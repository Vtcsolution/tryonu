/** Which build of the website this server runs; open tabs compare it with
 * their own (components/app/VersionWatch.tsx) to load fresh after an update. */
export const dynamic = "force-dynamic";

export function GET() {
  return Response.json({ id: process.env.NEXT_PUBLIC_BUILD_ID ?? "" }, { headers: { "Cache-Control": "no-store" } });
}
