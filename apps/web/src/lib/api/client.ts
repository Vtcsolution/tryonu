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

// The access-token cookie only lives 30 minutes; the refresh-token cookie
// lives 30 days and is rolled forward on every use (see
// app/services/auth_service.rotate_refresh_token). Without this, a 401 from
// an expired access token looked identical to "actually signed out" and
// booted the user every 30 minutes instead of every 30 days. Concurrent
// 401s share one in-flight refresh instead of each firing their own.
let refreshInFlight: Promise<boolean> | null = null;

function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
    })
      .then((r) => r.ok)
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

const NO_REFRESH_RETRY_PATHS = ["/api/v1/auth/refresh", "/api/v1/auth/login", "/api/v1/auth/register"];

export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, isFormData, signal, cache } = opts;

  const headers: Record<string, string> = {};
  if (!isFormData && body !== undefined) headers["Content-Type"] = "application/json";

  const requestBody = body === undefined ? undefined : isFormData ? (body as FormData) : JSON.stringify(body);
  const doFetch = () =>
    fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      credentials: "include",
      body: requestBody,
      signal,
      cache: cache ?? "no-store",
    });

  let res = await doFetch();

  if (res.status === 401 && !NO_REFRESH_RETRY_PATHS.some((p) => path.startsWith(p))) {
    const refreshed = await refreshSession();
    if (refreshed) res = await doFetch();
  }

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
/** A file upload that reports progress (0-100), e.g. a video. Same session
 * handling as apiFetch: an expired sign-in is refreshed once, then retried. */
export function uploadWithProgress<T>(path: string, form: FormData, onProgress: (pct: number) => void): Promise<T> {
  const send = () =>
    new Promise<{ status: number; body: unknown }>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API_BASE_URL}${path}`);
      xhr.withCredentials = true;
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
      };
      xhr.onload = () => {
        let body: unknown = null;
        try {
          body = JSON.parse(xhr.responseText);
        } catch {
          body = null;
        }
        resolve({ status: xhr.status, body });
      };
      xhr.onerror = () => reject(new ApiError(0, "Upload failed. Check your internet connection and try again."));
      xhr.send(form);
    });
  return (async () => {
    let res = await send();
    if (res.status === 401 && (await refreshSession())) res = await send();
    if (res.status >= 200 && res.status < 300) return res.body as T;
    const detail = (res.body as { detail?: unknown } | null)?.detail;
    if (res.status === 413) throw new ApiError(413, typeof detail === "string" ? detail : "That file is too big to upload.");
    throw new ApiError(res.status, typeof detail === "string" ? detail : "Upload failed. Please try again.");
  })();
}

export function resolveMediaUrl(url: string | null | undefined): string {
  if (!url) return "";
  return url.startsWith("/") ? `${API_BASE_URL}${url}` : url;
}

/** Smaller variant for grid thumbnails. Product images are stored at the
 * largest size (used as the try-on garment input); eBay serves the same
 * photo at fixed sizes, and 500px is ~9x lighter than 1600px. */
export function thumbnailUrl(url: string | null | undefined): string {
  const resolved = resolveMediaUrl(url);
  return resolved.replace(/(i\.ebayimg\.com\/.*\/s-l)\d+(\.\w+)$/, "$1500$2");
}

/** A retailer's product photo through TryOnU's own server (api/v1/img): some
 * shoppers' internet providers can't reach eBay's or AliExpress's image
 * servers, and this one they can. Our own media is returned as it is. */
export function relayedImageUrl(url: string | null | undefined, width = 600): string {
  const resolved = resolveMediaUrl(url);
  if (!resolved || (API_BASE_URL && resolved.startsWith(API_BASE_URL)) || !/^https?:\/\//.test(resolved)) return resolved;
  return `${API_BASE_URL}/api/v1/img?u=${encodeURIComponent(resolved)}&w=${width}`;
}

/** A small copy of one of our own stored pictures (a try-on, a search photo)
 * for thumbnail strips; other URLs are returned as they are. */
export function mediaThumb(url: string | null | undefined, width: 240 | 400 | 600 | 900 = 240): string {
  const resolved = resolveMediaUrl(url);
  if (!resolved || !resolved.includes("/media/") || !resolved.includes("sig=")) return resolved;
  return `${resolved}&w=${width}`;
}

export function affiliateGoUrl(productId: string, source?: string): string {
  const q = source ? `?source=${encodeURIComponent(source)}` : "";
  return `${API_BASE_URL}/api/v1/affiliate/go/${productId}${q}`;
}
