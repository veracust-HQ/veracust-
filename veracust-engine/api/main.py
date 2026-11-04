from __future__ import annotations

import asyncio
import hashlib
import os
import secrets
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")
import sys
sys.path.insert(0, str(BASE_DIR / "src"))
from src.pipeline import VeracustPipeline

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
MAX_UPLOAD_BYTES = int(os.getenv("VERACUST_MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))
ANON_CREDITS = int(os.getenv("VERACUST_ANONYMOUS_MONTHLY_CREDITS", "1000"))
CREDITS_PER_ANALYSIS = 10
ALLOWED_SUFFIXES = {".wav", ".mp3", ".m4a", ".flac"}
VISITOR_COOKIE = "vrc_visitor"
COOKIE_SECURE = os.getenv("VERACUST_COOKIE_SECURE", "false").lower() == "true"
CONFIG = os.getenv("VERACUST_CONFIG", str(BASE_DIR / "configs" / "default_config.yaml"))
CHECKPOINT = os.getenv("VERACUST_CHECKPOINT") or None

app = FastAPI(title="Veracust Inference API", version="2.0.0")
app.add_middleware(CORSMiddleware,
    allow_origins=[v.strip() for v in os.getenv("VERACUST_CORS_ORIGINS", "http://localhost:3000").split(",") if v.strip()],
    allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Idempotency-Key"])
pipeline: VeracustPipeline | None = None

class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=80)

class RefreshBody(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=4096)

class ApiKeyBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    expires_at: datetime | None = None

def _ready() -> bool:
    return bool(SUPABASE_URL and SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY)

def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

def _headers(prefer: str | None = None) -> dict[str, str]:
    if not _ready():
        raise HTTPException(503, "Supabase is not configured on the inference service.")
    # Send the project secret/service-role credential only as an API key.
    # Modern sb_secret_ keys are opaque and must NOT be sent as Bearer JWTs.
    # Legacy service_role JWTs are also accepted in the apikey header.
    h = {"apikey": SUPABASE_SERVICE_ROLE_KEY, "Content-Type": "application/json"}
    if prefer:
        h["Prefer"] = prefer
    return h

async def _db(method: str, path: str, params: dict | None = None,
              payload: Any = None, prefer: str | None = None):
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(25, connect=8)) as client:
            r = await client.request(method, f"{SUPABASE_URL}/rest/v1/{path}",
                headers=_headers(prefer), params=params, json=payload)
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Could not reach the Veracust database.") from exc
    if r.status_code >= 400:
        raise HTTPException(503, f"Database operation failed (HTTP {r.status_code}).")
    return r.json() if r.content else None

async def _auth(path: str, payload: dict, token: str | None = None):
    if not _ready():
        raise HTTPException(503, "Supabase is not configured on the inference service.")
    h = {"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(f"{SUPABASE_URL}/auth/v1/{path}", headers=h, json=payload)
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Could not reach Supabase Auth.") from exc
    return r.status_code, r.json() if r.content else {}

async def _user(token: str):
    async with httpx.AsyncClient(timeout=12) as client:
        r = await client.get(f"{SUPABASE_URL}/auth/v1/user",
            headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"})
    return r.json() if r.status_code == 200 else None

async def _account(account_id: str):
    rows = await _db("GET", "usage_accounts", {"select": "*", "id": f"eq.{account_id}", "limit": "1"})
    return rows[0] if rows else None

async def _identity(request: Request, response: Response, allow_key: bool = True):
    bearer = request.headers.get("authorization", "")
    token = bearer[7:].strip() if bearer.lower().startswith("bearer ") else request.cookies.get("vrc_access", "")
    if token.startswith("vrc_live_"):
        if not allow_key:
            raise HTTPException(401, "Use account login to manage API keys.")
        rows = await _db("GET", "api_keys", {"select": "id,account_id,expires_at,revoked_at",
            "key_hash": f"eq.{_hash(token)}", "revoked_at": "is.null", "limit": "1"})
        if not rows:
            raise HTTPException(401, "Invalid or revoked API key.")
        key = rows[0]
        if key.get("expires_at") and datetime.fromisoformat(key["expires_at"].replace("Z", "+00:00")) <= datetime.now(timezone.utc):
            raise HTTPException(401, "API key expired.")
        account = await _account(key["account_id"])
        if not account or not account.get("is_active"):
            raise HTTPException(403, "Usage account is inactive.")
        await _db("PATCH", "api_keys", {"id": f"eq.{key['id']}"}, {"last_used_at": datetime.now(timezone.utc).isoformat()})
        return account, account.get("user_id"), "api_key"
    if token:
        user = await _user(token)
        if not user:
            raise HTTPException(401, "Login session is invalid or expired.")
        uid = user["id"]
        profiles = await _db("GET", "profiles", {"select": "role", "user_id": f"eq.{uid}", "limit": "1"})
        role = profiles[0].get("role", "customer") if profiles else "customer"
        rows = await _db("GET", "usage_accounts", {"select": "*", "user_id": f"eq.{uid}", "limit": "1"})
        if not rows:
            rows = await _db("POST", "usage_accounts", payload={"user_id": uid,
                "account_type": "customer", "credits_remaining": 0, "monthly_allowance": 0},
                prefer="return=representation")
        account = rows[0]
        desired = "admin" if role == "admin" else "customer"
        if account.get("account_type") != desired:
            updated = await _db("PATCH", "usage_accounts", {"id": f"eq.{account['id']}"},
                {"account_type": desired}, "return=representation")
            if updated:
                account = updated[0]
        return account, uid, "user"
    visitor = request.cookies.get(VISITOR_COOKIE)
    if not visitor or len(visitor) < 32:
        visitor = secrets.token_urlsafe(32)
        response.set_cookie(VISITOR_COOKIE, visitor, max_age=31536000, httponly=True,
            secure=COOKIE_SECURE, samesite="lax", path="/")
    rows = await _db("GET", "usage_accounts", {"select": "*",
        "anonymous_key_hash": f"eq.{_hash(visitor)}", "limit": "1"})
    if not rows:
        rows = await _db("POST", "usage_accounts", payload={
            "anonymous_key_hash": _hash(visitor), "account_type": "anonymous",
            "credits_remaining": ANON_CREDITS, "monthly_allowance": ANON_CREDITS},
            prefer="return=representation")
    return rows[0], None, "anonymous"

def _pipeline():
    global pipeline
    if pipeline is None:
        pipeline = VeracustPipeline(CONFIG, CHECKPOINT)
    return pipeline

def _balance(row: dict):
    admin = row.get("account_type") == "admin"
    return {"accountType": row.get("account_type"), "unlimited": admin,
        "creditsRemaining": None if admin else row.get("credits_remaining", 0),
        "monthlyAllowance": None if admin else row.get("monthly_allowance", 0),
        "creditsPerAnalysis": CREDITS_PER_ANALYSIS,
        "analysesRemaining": None if admin else row.get("credits_remaining", 0) // CREDITS_PER_ANALYSIS,
        "periodStart": row.get("period_start"), "periodEnd": row.get("period_end"),
        "active": row.get("is_active", True)}

@app.get("/health")
async def health():
    return {"status": "ok", "engine": "Veracust", "supabase_configured": _ready(),
        "checkpoint_configured": bool(CHECKPOINT), "credits_per_analysis": CREDITS_PER_ANALYSIS}

@app.post("/api/v1/auth/signup")
async def signup(body: Credentials):
    status, data = await _auth("signup", {"email": body.email.strip().lower(),
        "password": body.password, "data": {"name": body.display_name} if body.display_name else {}})
    if status >= 400:
        raise HTTPException(400, data.get("msg") or data.get("message") or "Signup failed.")
    return {"success": True, "requiresEmailConfirmation": not bool(data.get("access_token")), **data}

@app.post("/api/v1/auth/login")
async def login(body: Credentials):
    status, data = await _auth("token?grant_type=password", {"email": body.email.strip().lower(), "password": body.password})
    if status >= 400 or not data.get("access_token"):
        raise HTTPException(401, data.get("msg") or data.get("message") or "Invalid credentials.")
    return {"success": True, **data}

@app.post("/api/v1/auth/refresh")
async def refresh(body: RefreshBody):
    status, data = await _auth("token?grant_type=refresh_token", {"refresh_token": body.refresh_token})
    if status >= 400 or not data.get("access_token"):
        raise HTTPException(401, "Session expired; sign in again.")
    return {"success": True, **data}

@app.post("/api/v1/auth/logout")
async def logout(request: Request):
    token = request.headers.get("authorization", "")
    token = token[7:].strip() if token.lower().startswith("bearer ") else ""
    if token:
        await _auth("logout", {}, token)
    return {"success": True}

@app.get("/api/v1/account")
async def account(request: Request, response: Response):
    row, _, kind = await _identity(request, response)
    rows = await _db("POST", "rpc/refresh_veracust_account", payload={"p_account_id": row["id"]})
    if not rows:
        raise HTTPException(404, "Usage account not found.")
    return {"success": True, "accountId": row["id"], "identity": kind, "usage": _balance(rows[0])}

@app.get("/api/v1/analyses")
async def analyses(request: Request, response: Response, limit: int = 50, offset: int = 0):
    row, _, _ = await _identity(request, response)
    items = await _db("GET", "analyses", {"select": "id,status,original_filename,verdict,confidence_score,created_at,completed_at,credits_charged,report",
        "account_id": f"eq.{row['id']}", "order": "created_at.desc",
        "limit": str(max(1, min(limit, 100))), "offset": str(max(0, offset))})
    return {"success": True, "items": items or []}

@app.get("/api/v1/api-keys")
async def list_keys(request: Request, response: Response):
    row, uid, kind = await _identity(request, response, False)
    if kind != "user":
        raise HTTPException(401, "Sign in to manage API keys.")
    items = await _db("GET", "api_keys", {"select": "id,name,key_prefix,last_used_at,expires_at,revoked_at,created_at",
        "account_id": f"eq.{row['id']}", "order": "created_at.desc"})
    return {"success": True, "items": items or []}

@app.post("/api/v1/api-keys")
async def create_key(body: ApiKeyBody, request: Request, response: Response):
    row, uid, kind = await _identity(request, response, False)
    if kind != "user":
        raise HTTPException(401, "Sign in to create an API key.")
    expiry = body.expires_at
    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry and expiry <= datetime.now(timezone.utc):
        raise HTTPException(400, "Expiry must be in the future.")
    secret = "vrc_live_" + secrets.token_urlsafe(32)
    items = await _db("POST", "api_keys", payload={"account_id": row["id"], "created_by": uid,
        "name": body.name.strip(), "key_prefix": secret[:16], "key_hash": _hash(secret),
        "expires_at": expiry.isoformat() if expiry else None}, prefer="return=representation")
    item = items[0]
    return {"success": True, "item": {"id": item["id"], "name": item["name"],
        "keyPrefix": item["key_prefix"], "createdAt": item["created_at"]},
        "apiKey": secret, "warning": "Copy this key now; it is only shown once."}

@app.delete("/api/v1/api-keys/{key_id}")
async def revoke_key(key_id: str, request: Request, response: Response):
    row, _, kind = await _identity(request, response, False)
    if kind != "user":
        raise HTTPException(401, "Sign in to revoke API keys.")
    items = await _db("PATCH", "api_keys", {"id": f"eq.{key_id}",
        "account_id": f"eq.{row['id']}", "revoked_at": "is.null"},
        {"revoked_at": datetime.now(timezone.utc).isoformat()}, "return=representation")
    if not items:
        raise HTTPException(404, "API key not found or already revoked.")
    return {"success": True, "revoked": True}

@app.post("/api/v1/detect")
async def detect(request: Request, response: Response, file: UploadFile = File(...)):
    row, uid, kind = await _identity(request, response)
    filename = Path(file.filename or "recording.wav").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(415, "Use WAV, MP3, M4A or FLAC.")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(400, "Uploaded audio is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Audio exceeds the upload limit.")
    aid = str(uuid.uuid4())
    await _db("POST", "analyses", payload={"id": aid, "account_id": row["id"], "user_id": uid,
        "status": "processing", "original_filename": filename, "mime_type": file.content_type,
        "file_size_bytes": len(content), "audio_sha256": hashlib.sha256(content).hexdigest(),
        "credits_charged": CREDITS_PER_ANALYSIS}, prefer="return=representation")
    charged = await _db("POST", "rpc/consume_veracust_credits", payload={
        "p_account_id": row["id"], "p_analysis_id": aid, "p_idempotency_key": f"analysis:{aid}:charge"})
    charge = charged[0] if charged else {"success": False, "reason": "charge_failed"}
    if not charge.get("success"):
        await _db("DELETE", "analyses", {"id": f"eq.{aid}"})
        code = 402 if charge.get("reason") == "insufficient_credits" else 403
        raise HTTPException(code, {"code": charge.get("reason"), "creditsRemaining": charge.get("credits_remaining", 0)})
    temp_path = None
    started = time.perf_counter()
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            temp_path = Path(tmp.name)
        report = await asyncio.to_thread(_pipeline().analyze, temp_path)
        elapsed = int((time.perf_counter() - started) * 1000)
        deep = report.get("forensic_trace", {}).get("deep", {})
        probability = float(report.get("confidence_score", 0.0))
        verdict = "synthetic" if report.get("is_synthetic") else "bonafide"
        analysis = {"id": aid, "fileName": filename, "createdAt": datetime.now(timezone.utc).isoformat(),
            "status": "completed", "verdict": verdict,
            "riskLevel": "high" if probability >= .8 else "medium" if probability >= .55 else "low",
            "manipulationProbability": round(probability * 100, 1), "confidence": round(probability * 100, 1),
            "latencyMs": elapsed, "audioSaved": False, "transcriptSaved": False,
            "simulated": False, "engineReport": report,
            "evidence": {"digitalFootprints": report.get("forensic_trace", {}).get("check0", {}),
                "biologicalTelemetry": report.get("forensic_trace", {}).get("biology", {}),
                "deepLearning": {"available": deep.get("available", False), "notes": deep.get("reason")}}}
        await _db("PATCH", "analyses", {"id": f"eq.{aid}"}, {"status": "completed",
            "verdict": verdict, "confidence_score": probability * 100,
            "duration_seconds": report.get("duration_seconds"), "engine_version": report.get("version"),
            "report": analysis, "credits_charged": charge.get("credits_charged", 0),
            "completed_at": datetime.now(timezone.utc).isoformat()})
        result = Response()
        payload = {"success": True, "product": "Veracust Enterprise API", "schemaVersion": "2.0.0",
            "analysis": analysis, "usage": {"creditsCharged": charge.get("credits_charged", 0),
            "creditsRemaining": None if row.get("account_type") == "admin" else charge.get("credits_remaining"),
            "unlimited": row.get("account_type") == "admin"}}
        from fastapi.responses import JSONResponse
        out = JSONResponse(payload, headers={"Cache-Control": "no-store"})
        for h, v in response.raw_headers:
            if h.lower() == b"set-cookie":
                out.raw_headers.append((h, v))
        return out
    except Exception as exc:
        await _db("POST", "rpc/refund_veracust_analysis", payload={
            "p_account_id": row["id"], "p_analysis_id": aid,
            "p_idempotency_key": f"analysis:{aid}:refund"})
        await _db("PATCH", "analyses", {"id": f"eq.{aid}"}, {
            "status": "failed", "error_code": type(exc).__name__, "credits_charged": 0,
            "completed_at": datetime.now(timezone.utc).isoformat()})
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(422, f"Analysis failed: {type(exc).__name__}. Check backend logs.") from exc
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        await file.close()
