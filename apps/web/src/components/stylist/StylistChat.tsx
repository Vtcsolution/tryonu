"use client";

import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { VoiceInputButton } from "@/components/ui/VoiceInputButton";
import { ApiError, affiliateGoUrl, resolveMediaUrl } from "@/lib/api/client";
import { products as productsApi, stylist as stylistApi, wardrobe as wardrobeApi } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";
import type { LiveProduct, Product, StylistResponse } from "@/lib/api/types";

const PROMPT_SUGGESTIONS = [
  "Build me a wedding outfit under $400",
  "What should I wear to a business meeting?",
  "Casual streetwear under $150",
  "Something for a summer evening out",
];

export function StylistChat() {
  const router = useRouter();
  const { user, isLoading: sessionLoading } = useSession();
  const qc = useQueryClient();

  const [prompt, setPrompt] = useState("");
  const [budgetMax, setBudgetMax] = useState("");
  const [wardrobeItemId, setWardrobeItemId] = useState("");
  const [thread, setThread] = useState<StylistResponse[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!sessionLoading && !user) router.replace("/sign-in?next=/stylist");
  }, [sessionLoading, user, router]);

  const historyQuery = useQuery({
    queryKey: ["stylist", "history"],
    queryFn: stylistApi.history,
    enabled: !!user,
  });

  const wardrobeQuery = useQuery({
    queryKey: ["wardrobe"],
    queryFn: wardrobeApi.list,
    enabled: !!user,
  });

  useEffect(() => {
    if (historyQuery.data) setThread([...historyQuery.data].reverse());
  }, [historyQuery.data]);

  const ask = useMutation({
    mutationFn: stylistApi.ask,
    onSuccess: (res) => {
      setThread((t) => [...t, res]);
      setPrompt("");
      qc.invalidateQueries({ queryKey: ["stylist", "history"] });
    },
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thread.length, ask.isPending]);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || ask.isPending) return;
    const budget = Number(budgetMax);
    ask.mutate({
      prompt: prompt.trim(),
      budget_max_cents: budgetMax && !Number.isNaN(budget) ? Math.round(budget * 100) : undefined,
      wardrobe_item_id: wardrobeItemId || undefined,
      max_items: 6,
    });
  };

  if (sessionLoading || !user) {
    return (
      <section className="mx-auto w-[min(880px,calc(100%-42px))] py-24 text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
      </section>
    );
  }

  return (
    <section className="mx-auto flex w-[min(880px,calc(100%-42px))] flex-col py-14 md:py-20">
      <h1 className="font-display text-[clamp(26px,4vw,40px)] leading-tight text-ink">
        Your AI <em>fashion stylist</em>
      </h1>
      <p className="mt-3 max-w-lg text-[15px] leading-relaxed text-muted">
        Ask for an outfit, an occasion look, or a budget — every recommendation comes straight
        from the real product catalog. Never invented.
      </p>

      <div className="mt-8 flex flex-col gap-6">
        {thread.length === 0 && !historyQuery.isLoading && (
          <div className="rounded-[22px] border border-dashed border-line p-6">
            <p className="text-[13px] font-semibold text-ink-soft">Try asking:</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {PROMPT_SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setPrompt(s)}
                  className="rounded-full border border-line px-3 py-1.5 text-[13px] text-ink-soft transition-colors hover:border-sage hover:text-sage-deep"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {thread.map((entry) => (
          <StylistExchange key={entry.id} entry={entry} />
        ))}

        {ask.isPending && (
          <div className="flex items-center gap-2 self-start rounded-full border border-line px-4 py-2 text-[13px] text-muted">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-sage" />
            Styling your look…
          </div>
        )}

        {ask.isError && (
          <p role="alert" className="text-[13px] text-[#a4553f]">
            {ask.error instanceof ApiError ? ask.error.detail : "Couldn't reach the stylist. Please try again."}
          </p>
        )}

        <div ref={bottomRef} />
      </div>

      {wardrobeQuery.data && wardrobeQuery.data.length > 0 && (
        <div className="mt-6 flex flex-wrap items-center gap-2 text-[12.5px]">
          <span className="text-faint">Build around:</span>
          <select
            value={wardrobeItemId}
            onChange={(e) => setWardrobeItemId(e.target.value)}
            className="h-8 rounded-full border border-line-strong bg-paper px-3 text-[12.5px] text-ink-soft"
          >
            <option value="">Nothing specific</option>
            {wardrobeQuery.data.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
      )}

      <form
        onSubmit={onSubmit}
        className="sticky bottom-4 mt-3 flex flex-col gap-2 rounded-[26px] border border-line bg-surface p-2 shadow-lift"
      >
        <div className="flex items-center gap-1.5">
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="e.g. black formal outfit for a wedding under $300"
            className="h-11 flex-1 rounded-full bg-transparent px-3 text-[14px] text-ink outline-none placeholder:text-faint"
          />
          <VoiceInputButton onTranscript={(text) => setPrompt((p) => (p ? `${p} ${text}` : text))} />
          <button
            type="submit"
            disabled={!prompt.trim() || ask.isPending}
            aria-label="Ask stylist"
            className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-sage text-white transition-opacity disabled:opacity-40"
          >
            {ask.isPending ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
            ) : (
              <span aria-hidden="true">↑</span>
            )}
          </button>
        </div>
        <div className="flex items-center gap-2 border-t border-line/70 px-1.5 pt-2">
          <label className="flex items-center gap-1.5 text-[12.5px] text-faint">
            Budget
            <input
              type="number"
              min={0}
              value={budgetMax}
              onChange={(e) => setBudgetMax(e.target.value)}
              placeholder="Max $"
              className="h-8 w-20 rounded-full border border-line-strong bg-paper px-3 text-[13px] text-ink outline-none placeholder:text-faint focus:border-sage focus:ring-2 focus:ring-sage/25"
            />
          </label>
        </div>
      </form>
    </section>
  );
}

function StylistExchange({ entry }: { entry: StylistResponse }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="self-end rounded-[18px] rounded-br-sm bg-sage px-4 py-2.5 text-[14px] text-white sm:max-w-[75%]">
        {entry.prompt}
      </div>

      <div className="self-start rounded-[18px] rounded-bl-sm border border-line bg-surface px-4 py-3.5 sm:max-w-[85%]">
        <p className="text-[14px] leading-relaxed text-ink">{entry.summary}</p>

        {entry.outfit && (
          <div className="mt-3 rounded-[16px] border border-line bg-paper-2 p-3">
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-faint">
                Complete outfit · {(entry.outfit.total_price_cents / 100).toFixed(2)}
              </p>
              {entry.outfit.compatibility_score != null && (
                <span
                  className={`text-[12px] font-semibold ${
                    entry.outfit.compatibility_score >= 65 ? "text-sage-deep" : "text-[#a4553f]"
                  }`}
                >
                  {entry.outfit.compatibility_score}% match
                </span>
              )}
            </div>
            {entry.outfit.compatibility_notes && entry.outfit.compatibility_notes.length > 0 && (
              <ul className="mt-1.5 space-y-1 text-[11.5px] text-muted">
                {entry.outfit.compatibility_notes.map((n) => (
                  <li key={n}>· {n}</li>
                ))}
              </ul>
            )}
            <Button
              href={`/try?outfit=${entry.outfit.id}`}
              size="sm"
              className="mt-3 !h-8 w-full !text-[12px]"
            >
              Try this outfit on
            </Button>
          </div>
        )}

        {entry.products.length > 0 && (
          <div className="mt-3 grid grid-cols-2 gap-2.5 sm:grid-cols-3">
            {entry.products.map((p) => (
              <StylistProductCard key={p.id} product={p} alternatives={entry.alternatives[p.id] ?? []} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StylistProductCard({ product, alternatives }: { product: Product; alternatives: LiveProduct[] }) {
  const thumb = resolveMediaUrl(product.images[0]?.url);
  const shopAlternative = useMutation({
    mutationFn: (item: LiveProduct) =>
      productsApi.selectLive({
        query: item.search_term ?? item.name,
        retailer_slug: item.retailer_slug,
        retailer_product_id: item.retailer_product_id,
      }),
    onSuccess: (p) => window.open(affiliateGoUrl(p.id, "stylist"), "_blank", "noopener,noreferrer"),
  });

  return (
    <div className="overflow-hidden rounded-[16px] border border-line bg-surface">
      <div className="relative aspect-[3/4] bg-paper-2">
        {thumb && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={thumb} alt={product.name} className="h-full w-full object-cover object-top" />
        )}
      </div>
      <div className="p-2.5">
        <p className="truncate text-[12px] font-semibold text-ink">{product.name}</p>
        <p className="mt-0.5 text-[11px] text-muted">
          {(product.price_cents / 100).toFixed(2)} {product.currency.toUpperCase()}
        </p>
        {alternatives.length > 0 && (
          <div className="mt-2 flex gap-1.5 overflow-x-auto pb-0.5">
            {alternatives.map((alt) => (
              <button
                key={`${alt.retailer_slug}:${alt.retailer_product_id}`}
                type="button"
                disabled={shopAlternative.isPending}
                onClick={() => shopAlternative.mutate(alt)}
                title={`${alt.name} — ${(alt.price_cents / 100).toFixed(2)} ${alt.currency.toUpperCase()}`}
                className="shrink-0 rounded-full border border-line px-2 py-0.5 text-[10px] text-ink-soft transition-colors hover:border-sage disabled:opacity-60"
              >
                {(alt.price_cents / 100).toFixed(0)} {alt.currency.toUpperCase()}
              </button>
            ))}
          </div>
        )}
        <div className="mt-2 flex gap-1.5">
          <Button href={`/try?product=${product.id}`} size="sm" variant="outline" className="!h-8 flex-1 !px-2 !text-[11px]">
            Try it on
          </Button>
          <Button href={affiliateGoUrl(product.id, "stylist")} size="sm" className="!h-8 flex-1 !px-2 !text-[11px]">
            Shop
          </Button>
        </div>
      </div>
    </div>
  );
}
