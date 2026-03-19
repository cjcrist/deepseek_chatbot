import type { NextRequest } from "next/server";

/** Server-side backend base URL (Compose sets this to http://chatbot:8000). */
const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

function forwardCookie(request: NextRequest): Record<string, string> {
  const cookie = request.headers.get("cookie");
  return cookie ? { cookie } : {};
}

/**
 * Proxies chat messages to FastAPI without buffering the body so SSE streams
 * (stream: true) reach the browser. Generic rewrites in next.config.ts buffer
 * long responses; this route takes precedence for this path.
 */
export async function GET(
  request: NextRequest,
  context: { params: Promise<{ chatId: string }> },
) {
  const { chatId } = await context.params;
  const search = request.nextUrl.search;
  const url = `${backendUrl}/chats/${encodeURIComponent(chatId)}/messages${search}`;

  const res = await fetch(url, {
    method: "GET",
    headers: {
      ...forwardCookie(request),
    },
    cache: "no-store",
  });

  const text = await res.text();
  const headers = new Headers();
  const ct = res.headers.get("content-type");
  if (ct) headers.set("Content-Type", ct);

  return new Response(text, { status: res.status, headers });
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ chatId: string }> },
) {
  const { chatId } = await context.params;
  const url = `${backendUrl}/chats/${encodeURIComponent(chatId)}/messages`;
  const body = await request.text();

  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...forwardCookie(request),
    },
    body,
    cache: "no-store",
  });

  const out = new Headers();
  const ct = res.headers.get("content-type");
  if (ct) out.set("Content-Type", ct);
  const cc = res.headers.get("cache-control");
  if (cc) out.set("Cache-Control", cc);
  const xa = res.headers.get("x-accel-buffering");
  if (xa) out.set("X-Accel-Buffering", xa);

  return new Response(res.body, {
    status: res.status,
    headers: out,
  });
}
