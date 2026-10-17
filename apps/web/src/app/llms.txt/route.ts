import { llmsText } from "@/lib/llmsText";

export const revalidate = 3600;

/** A plain-text guide to TryOnU for AI assistants (llmstxt.org). */
export async function GET() {
  return new Response(await llmsText(false), { headers: { "Content-Type": "text/plain; charset=utf-8" } });
}
