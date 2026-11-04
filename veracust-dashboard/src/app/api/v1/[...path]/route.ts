import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function proxy(req: NextRequest, context: { params: { path: string[] } }) {
  const base = process.env.VERACUST_API_URL;
  if (!base) return NextResponse.json({ detail: "VERACUST_API_URL is not configured." }, { status: 503 });
  // This catch-all is mounted at /api/v1/[...path], while FastAPI routes
  // are mounted at /api/v1/*. Preserve that prefix when forwarding upstream.
  const path = (context.params.path || []).join("/");
  const url = new URL(`api/v1/${path}`, base.endsWith("/") ? base : base + "/");
  url.search = req.nextUrl.search;
  const headers = new Headers();
  for (const key of ["authorization", "content-type", "cookie", "idempotency-key"]) {
    const value = req.headers.get(key);
    if (value) headers.set(key, value);
  }
  const body = ["GET", "HEAD"].includes(req.method) ? undefined : await req.arrayBuffer();
  try {
    const upstream = await fetch(url, { method: req.method, headers, body, cache: "no-store" });
    const responseHeaders = new Headers();
    for (const key of ["content-type", "cache-control", "set-cookie"]) {
      const value = upstream.headers.get(key);
      if (value) responseHeaders.set(key, value);
    }
    return new NextResponse(await upstream.arrayBuffer(), { status: upstream.status, headers: responseHeaders });
  } catch {
    return NextResponse.json({ detail: "Could not reach the Veracust inference API." }, { status: 502 });
  }
}
export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
