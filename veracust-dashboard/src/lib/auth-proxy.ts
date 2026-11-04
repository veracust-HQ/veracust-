import { NextRequest, NextResponse } from "next/server";

const API = process.env.VERACUST_API_BASE_URL || process.env.VERACUST_API_URL;
const ACCESS = "vrc_access";
const REFRESH = "vrc_refresh";

type UpstreamResult = { res: Response; data: Record<string, any>; parseError?: boolean };

async function call(action: string, body?: unknown, token?: string): Promise<UpstreamResult> {
  if (!API) throw new Error("The authentication API URL is not configured on the dashboard.");
  const base = API.endsWith("/") ? API.slice(0, -1) : API;
  const headers = new Headers({ "Accept": "application/json", "Content-Type": "application/json" });
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20_000);
  try {
    const res = await fetch(`${base}/api/v1/auth/${action}`, {
      method: "POST",
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
      signal: controller.signal,
    });
    const raw = await res.text();
    try {
      const parsed = raw ? JSON.parse(raw) : {};
      return { res, data: parsed && typeof parsed === "object" ? parsed : {}, parseError: false };
    } catch {
      return { res, data: {}, parseError: true };
    }
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error("The authentication service timed out. Please retry in a moment.");
    }
    throw new Error("Could not reach the Veracust authentication service. It may be starting after inactivity; please retry shortly.");
  } finally {
    clearTimeout(timeout);
  }
}

function setCookies(out: NextResponse, data: Record<string, any>) {
  const secure = process.env.NODE_ENV === "production";
  if (data.access_token) {
    out.cookies.set(ACCESS, data.access_token, {
      httpOnly: true, secure, sameSite: "lax", path: "/",
      maxAge: Math.max(60, Number(data.expires_in || 3600)),
    });
  }
  if (data.refresh_token) {
    out.cookies.set(REFRESH, data.refresh_token, {
      httpOnly: true, secure, sameSite: "lax", path: "/", maxAge: 30 * 24 * 60 * 60,
    });
  }
}

export async function authAction(
  req: NextRequest,
  action: "login" | "signup" | "refresh" | "logout",
) {
  try {
    let body: unknown;
    let token: string | undefined;
    if (action === "login" || action === "signup") body = await req.json();
    if (action === "refresh") {
      const value = req.cookies.get(REFRESH)?.value;
      if (!value) {
        const out = NextResponse.json(
          { success: false, error: "Your session has expired. Please sign in again." },
          { status: 401 },
        );
        out.cookies.delete(ACCESS);
        out.cookies.delete(REFRESH);
        return out;
      }
      body = { refresh_token: value };
    }
    if (action === "logout") token = req.cookies.get(ACCESS)?.value;

    const { res, data, parseError } = await call(action, body, token);
    if (!res.ok) {
      const upstreamMessage = data.detail || data.msg || data.message || data.error;
      const error = typeof upstreamMessage === "string"
        ? upstreamMessage
        : parseError
          ? `The authentication service returned an unreadable response (HTTP ${res.status}). Please retry; if it continues, contact support with this status code.`
          : `Authentication request failed (HTTP ${res.status}).`;
      const out = NextResponse.json(
        { success: false, error },
        { status: res.status, headers: { "Cache-Control": "no-store" } },
      );
      if (action === "refresh") {
        out.cookies.delete(ACCESS);
        out.cookies.delete(REFRESH);
      }
      return out;
    }

    if ((action === "login" || action === "refresh") && !data.access_token) {
      return NextResponse.json(
        { success: false, error: "The authentication service did not return a valid session. Please retry." },
        { status: 502, headers: { "Cache-Control": "no-store" } },
      );
    }

    const out = NextResponse.json(
      {
        success: true,
        message: data.message,
        requiresEmailConfirmation: data.requiresEmailConfirmation,
        user: data.user,
      },
      { headers: { "Cache-Control": "no-store" } },
    );
    if (action === "logout") {
      out.cookies.delete(ACCESS);
      out.cookies.delete(REFRESH);
    } else {
      setCookies(out, data);
    }
    return out;
  } catch (error) {
    const message = error instanceof Error
      ? error.message
      : "An unexpected authentication error occurred.";
    return NextResponse.json(
      { success: false, error: message },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
