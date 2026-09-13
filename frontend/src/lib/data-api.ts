/**
 * Same-origin client for the Next → agent data bridge.
 * Destinations load series without a chat turn.
 */

export class DataApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "DataApiError";
    this.status = status;
  }
}

export async function fetchData<T = unknown>(
  path: string,
  params?: Record<string, string | undefined | null>,
): Promise<T> {
  const qs = new URLSearchParams();
  qs.set("path", path);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null || value === "") continue;
      qs.set(key, value);
    }
  }

  const response = await fetch(`/api/data?${qs.toString()}`, {
    method: "GET",
    headers: { Accept: "application/json" },
    cache: "no-store",
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") detail = payload.detail;
    } catch {
      /* ignore */
    }
    throw new DataApiError(detail || `HTTP ${response.status}`, response.status);
  }

  return (await response.json()) as T;
}
