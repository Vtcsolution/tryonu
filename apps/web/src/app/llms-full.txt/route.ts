import { llmsText } from "@/lib/llmsText";

export const revalidate = 3600;

/** Everything in llms.txt, plus every FAQ answer and topic page in one file. */
export async function GET() {
  return new Response(await llmsText(true), { headers: { "Content-Type": "text/plain; charset=utf-8" } });
}
