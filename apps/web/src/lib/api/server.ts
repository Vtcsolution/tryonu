/**
 * Server-Component-only fetch helper. Separate from client.ts's
 * `API_BASE_URL` because in Docker the browser and the Next.js server
 * reach the API differently: the browser needs the publicly exposed
 * `NEXT_PUBLIC_API_URL` (e.g. http://localhost:8000), while the Next
 * server itself can talk to the `api` container directly over the
 * compose network (`API_INTERNAL_URL=http://api:8000`) — set that only in
 * docker-compose; locally both default to the same address.
 *
 * Never throws: marketing pages that opportunistically show live catalog
 * data must still render (with their existing static fallback) if the API
 * is briefly unreachable.
 */

const INTERNAL_BASE =
  process.env.API_INTERNAL_URL?.replace(/\/$/, "") ||
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export async function serverFetch<T>(
  path: string,
  opts: { revalidateSeconds?: number } = {},
): Promise<T | null> {
  try {
    const res = await fetch(`${INTERNAL_BASE}${path}`, {
      next: { revalidate: opts.revalidateSeconds ?? 60 },
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}
