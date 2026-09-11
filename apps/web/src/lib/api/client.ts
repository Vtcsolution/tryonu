/**
 * Thin fetch wrapper for the TryOnU API. Always sends credentials (the
 * httpOnly access/refresh cookies the API sets on login) and normalizes
 * error responses into `ApiError` so callers get a consistent shape for
 * loading/error/empty states.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  isFormData?: boolean;
  signal?: AbortSignal;
  cache?: RequestCache;
};

export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, isFormData, signal, cache } = opts;

  const headers: Record<string, string> = {};
  if (!isFormData && body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    credentials: "include",
    body: body === undefined ? undefined : isFormData ? (body as FormData) : JSON.stringify(body),
    signal,
    cache: cache ?? "no-store",
  });

  if (res.status === 204) return undefined as T;

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json().catch(() => null) : null;

  if (!res.ok) {
    const detail =
      (data && (data.detail || (Array.isArray(data.errors) && data.errors[0]?.msg))) ||
      res.statusText ||
      "Something went wrong";
    throw new ApiError(res.status, String(detail));
  }

  return data as T;
}

/** Resolves an API-relative media URL (e.g. local-disk `/media/...`) to an
 * absolute one; leaves already-absolute URLs (S3/R2/CDN, Unsplash) alone. */
export function resolveMediaUrl(url: string | null | undefined): string {
  if (!url) return "";
  return url.startsWith("/") ? `${API_BASE_URL}${url}` : url;
}

export function affiliateGoUrl(productId: string, source?: string): string {
  const q = source ? `?source=${encodeURIComponent(source)}` : "";
  return `${API_BASE_URL}/api/v1/affiliate/go/${productId}${q}`;
}
