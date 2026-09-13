/**
 * Data bridge — proxies catalog fetches to the Python agent /api/data.
 * Browser must not call FastAPI directly (same pattern as CopilotKit).
 */

const AGENT_URL =
  process.env.AGENT_URL ?? "http://127.0.0.1:8000/argentina_insights";

function agentBaseUrl(): string {
  const trimmed = AGENT_URL.replace(/\/$/, "");
  if (trimmed.endsWith("/argentina_insights")) {
    return trimmed.slice(0, -"/argentina_insights".length) || "http://127.0.0.1:8000";
  }
  return process.env.AGENT_BASE_URL ?? "http://127.0.0.1:8000";
}

export async function GET(request: Request): Promise<Response> {
  const incoming = new URL(request.url);
  if (!incoming.searchParams.get("path")) {
    return Response.json({ detail: "Missing path query param" }, { status: 400 });
  }

  const target = new URL("/api/data", agentBaseUrl());
  incoming.searchParams.forEach((value, key) => {
    target.searchParams.append(key, value);
  });

  try {
    const upstream = await fetch(target.toString(), {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    const body = await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: {
        "Content-Type":
          upstream.headers.get("Content-Type") ?? "application/json",
      },
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Upstream unreachable";
    return Response.json({ detail: message }, { status: 502 });
  }
}
