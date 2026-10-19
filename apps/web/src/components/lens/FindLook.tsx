"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ProductCard } from "@/components/product/ProductCard";
import { RECOMMENDED, fromTryOnUStore, shopName } from "@/components/try/shop";
import { ApiError, affiliateGoUrl, resolveMediaUrl } from "@/lib/api/client";
import { community, lens, outfits, products as productsApi, type LensItem, type LensMatch, type LensResult } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";

const STEPS = [
  "Looking at your photo…",
  "Finding each item: clothes, shoes, bags, jewellery…",
  "Searching TryOnU stores, eBay, AliExpress and more…",
  "Comparing the products with your photo…",
  "Putting the closest ones first…",
];
const BADGE: Record<LensMatch["match"], string> = { exact: "✓ Exact match", close: "Very close", similar: "Similar" };
// wearable items go into "Try the whole look"
const WEARABLE = new Set(["top", "bottom", "dress", "full_outfit", "outerwear", "shoes", "bag", "jewellery", "watch", "eyewear", "headwear", "scarf", "belt"]);

/** /find-look: search the shops with a photo, like Google Lens. */
export function FindLook() {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const { user, isLoading } = useSession();
  const [result, setResult] = useState<LensResult | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const started = useRef<string | null>(null);

  const run = useCallback(
    async (work: () => Promise<LensResult>, previewUrl: string | null) => {
      setError(null);
      setResult(null);
      setPreview(previewUrl);
      setBusy(true);
      setStep(0);
      try {
        const res = await work();
        setResult(res);
        qc.invalidateQueries({ queryKey: ["lens", "mine"] });
        router.replace(`/find-look?id=${res.id}`, { scroll: false });
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : "Something went wrong. Please try again.");
      } finally {
        setBusy(false);
      }
    },
    [qc, router],
  );

  // the steps move along while the search runs (it takes 10-20 seconds)
  useEffect(() => {
    if (!busy) return;
    const t = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 3500);
    return () => clearInterval(t);
  }, [busy]);

  // opened with ?id= (a saved search), ?post= (a community photo) or ?look= (one of my looks)
  useEffect(() => {
    if (!user) return;
    const id = params.get("id");
    const post = params.get("post");
    const look = params.get("look");
    const key = id ?? post ?? look;
    if (!key || started.current === key || result?.id === id) return;
    started.current = key;
    if (id) {
      lens.get(id).then(setResult).catch(() => setError("That search isn't here anymore."));
    } else if (post) {
      run(() => lens.from({ post_id: post }), null);
    } else if (look) {
      run(() => lens.from({ tryon_job_id: look }), null);
    }
  }, [params, user, run, result?.id]);

  const pickFile = (file: File | undefined) => {
    if (!file) return;
    if (!file.type.startsWith("image/") && !/\.(heic|heif)$/i.test(file.name)) {
      setError("Please choose a photo or a screenshot.");
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      setError("That photo is too big. Please use one under 15 MB.");
      return;
    }
    run(() => lens.search(file, () => undefined), URL.createObjectURL(file));
  };

  if (isLoading) return <div className="mx-auto my-24 h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />;

  return (
    <section className="tu-container py-8 md:py-12">
      {!result && !busy && <Intro signedIn={!!user} />}

      {!user ? (
        <div className="mx-auto mt-8 max-w-xl rounded-[22px] border border-line bg-surface p-6 text-center">
          <p className="text-[17px] font-semibold text-ink">Create a free account to search by photo</p>
          <p className="mt-1 text-[15px] text-muted">It takes a minute, and your first try-ons are free.</p>
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            <Link href="/sign-up?next=/find-look" className="inline-flex min-h-[48px] items-center rounded-full bg-sage px-6 text-[15.5px] font-semibold text-white hover:bg-sage-deep">
              Join free
            </Link>
            <Link href="/sign-in?next=/find-look" className="inline-flex min-h-[48px] items-center rounded-full border border-line-strong px-6 text-[15.5px] font-semibold text-ink">
              Sign in
            </Link>
          </div>
        </div>
      ) : busy ? (
        <Searching preview={preview} step={step} />
      ) : result ? (
        <Results
          result={result}
          onAgain={() => {
            setResult(null);
            setPreview(null);
            started.current = null;
            router.replace("/find-look", { scroll: false });
          }}
        />
      ) : (
        <Start onFile={pickFile} onLook={(jobId, url) => run(() => lens.from({ tryon_job_id: jobId }), resolveMediaUrl(url))} error={error} />
      )}
      {error && (busy || result) && <p role="alert" className="mt-4 text-center text-[15px] text-[#a4553f]">{error}</p>}
    </section>
  );
}

function Intro({ signedIn }: { signedIn: boolean }) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <p className="text-[13px] font-semibold uppercase tracking-[0.16em] text-sage-deep">Find the look</p>
      <h1 className="mt-2 font-display text-[clamp(32px,5vw,52px)] leading-[1.05] text-ink">
        Saw an outfit you love? <em>Find it.</em>
      </h1>
      <p className="mt-4 text-[17.5px] leading-relaxed text-ink-soft">
        Upload a photo or a screenshot. TryOnU finds every item in it (clothes, shoes, bags, jewellery) and shows you the same products, or
        the closest ones, from real shops. Then try them on yourself.
      </p>
      {!signedIn && (
        <ol className="mx-auto mt-6 grid max-w-xl gap-2 text-left text-[15px] text-ink-soft sm:grid-cols-3">
          <li className="rounded-xl border border-line bg-surface p-3"><b className="text-ink">1.</b> Upload a photo</li>
          <li className="rounded-xl border border-line bg-surface p-3"><b className="text-ink">2.</b> See each item and where to buy it</li>
          <li className="rounded-xl border border-line bg-surface p-3"><b className="text-ink">3.</b> Try it on yourself</li>
        </ol>
      )}
    </div>
  );
}

function Start({ onFile, onLook, error }: { onFile: (f: File | undefined) => void; onLook: (jobId: string, url: string) => void; error: string | null }) {
  const [drag, setDrag] = useState(false);
  const looks = useQuery({ queryKey: ["community", "my-looks"], queryFn: community.myLooks });
  const recent = useQuery({ queryKey: ["lens", "mine"], queryFn: lens.list });
  return (
    <div className="mx-auto mt-8 max-w-3xl">
      <label
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          onFile(e.dataTransfer.files?.[0]);
        }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-[24px] border-2 border-dashed px-6 py-12 text-center transition-colors ${
          drag ? "border-sage bg-sage-tint/30" : "border-line-strong bg-surface hover:border-sage"
        }`}
      >
        <input type="file" accept="image/*,.heic,.heif" className="sr-only" onChange={(e) => onFile(e.target.files?.[0])} />
        <span className="grid h-16 w-16 place-items-center rounded-full bg-sage text-white">
          <LensIcon size={30} />
        </span>
        <span className="mt-4 text-[19px] font-semibold text-ink">Upload a photo or screenshot</span>
        <span className="mt-1 text-[15px] text-muted">From Instagram, TikTok, a shop, a wedding, the street… or take one now</span>
        <span className="mt-5 inline-flex min-h-[48px] items-center rounded-full bg-sage px-6 text-[15.5px] font-semibold text-white">Choose a photo</span>
      </label>
      {error && <p role="alert" className="mt-3 text-center text-[15px] text-[#a4553f]">{error}</p>}

      {looks.data && looks.data.length > 0 && (
        <div className="mt-8">
          <p className="text-[16px] font-semibold text-ink">Or find the products in one of your looks</p>
          <div className="mt-3 flex gap-3 overflow-x-auto pb-2">
            {looks.data.slice(0, 12).map((l) => (
              <button
                key={l.job_id}
                type="button"
                onClick={() => onLook(l.job_id, l.image_url)}
                className="w-24 shrink-0 overflow-hidden rounded-xl border border-line hover:border-sage"
                title="Find the products in this look"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={resolveMediaUrl(l.image_url)} alt="One of your looks" loading="lazy" className="aspect-[3/4] w-full bg-paper-2 object-cover object-top" />
              </button>
            ))}
          </div>
        </div>
      )}

      {recent.data && recent.data.length > 0 && (
        <div className="mt-8">
          <p className="text-[16px] font-semibold text-ink">Your recent searches</p>
          <div className="mt-3 flex gap-3 overflow-x-auto pb-2">
            {recent.data.map((r) => (
              <Link key={r.id} href={`/find-look?id=${r.id}`} className="w-28 shrink-0 overflow-hidden rounded-xl border border-line bg-surface hover:border-sage">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={resolveMediaUrl(r.image_url)} alt="" loading="lazy" className="aspect-square w-full bg-paper-2 object-cover object-top" />
                <span className="block px-2 py-1.5 text-[12.5px] text-muted">{r.items} {r.items === 1 ? "item" : "items"} found</span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Searching({ preview, step }: { preview: string | null; step: number }) {
  return (
    <div className="mx-auto mt-8 flex max-w-md flex-col items-center text-center">
      <div className="relative w-full max-w-[320px] overflow-hidden rounded-[22px] border border-line bg-paper-2">
        {preview ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={preview} alt="Your photo" className="max-h-[420px] w-full object-contain" />
        ) : (
          <div className="aspect-[3/4] w-full" />
        )}
        <span aria-hidden="true" className="tu-scan absolute inset-x-0 h-16 bg-gradient-to-b from-transparent via-sage/35 to-transparent" />
      </div>
      <p className="mt-5 text-[17px] font-semibold text-ink" aria-live="polite">{STEPS[step]}</p>
      <div className="mt-3 flex gap-1.5" aria-hidden="true">
        {STEPS.map((_, i) => (
          <span key={i} className={`h-1.5 w-8 rounded-full transition-colors ${i <= step ? "bg-sage" : "bg-line"}`} />
        ))}
      </div>
      <p className="mt-3 text-[14px] text-muted">This takes about 15 seconds.</p>
    </div>
  );
}

function Results({ result, onAgain }: { result: LensResult; onAgain: () => void }) {
  const router = useRouter();
  const [active, setActive] = useState(0);
  const [sort, setSort] = useState<"best" | "price">("best");
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const item: LensItem | undefined = result.items[active];
  const matches = useMemo(() => {
    const list = [...(item?.matches ?? [])];
    if (sort === "price") list.sort((a, b) => a.product.price_cents - b.product.price_cents);
    return list;
  }, [item, sort]);

  const choose = async (m: LensMatch) =>
    productsApi.selectLive({ query: m.product.search_term ?? item?.query ?? m.product.name, retailer_slug: m.product.retailer_slug, retailer_product_id: m.product.retailer_product_id });

  const act = async (m: LensMatch, then: "try" | "shop") => {
    const key = `${m.product.retailer_slug}:${m.product.retailer_product_id}`;
    setError(null);
    setBusyKey(key);
    // opened at the click, so the browser doesn't block it as a pop-up
    const tab = then === "shop" ? window.open("about:blank", "_blank") : null;
    try {
      const p = await choose(m);
      if (then === "try") router.push(`/try?product=${p.id}`);
      else if (tab) tab.location.href = affiliateGoUrl(p.id, "lens");
      else window.open(affiliateGoUrl(p.id, "lens"), "_blank", "noopener");
    } catch (err) {
      tab?.close();
      setError(err instanceof ApiError ? err.detail : "That product isn't available anymore. Try another one.");
    } finally {
      setBusyKey(null);
    }
  };

  const wholeLook = useMutation({
    mutationFn: async () => {
      const wanted = result.items.filter((i) => WEARABLE.has(i.category) && i.matches.length > 0).slice(0, 10);
      // one after another: saving several new products of the same shop at once can collide;
      // an item whose best match is gone gets its next best (up to three tries)
      const items: { product_id: string; slot: "other" }[] = [];
      for (const it of wanted) {
        for (const m of it.matches.slice(0, 3)) {
          const p = await choose(m).catch(() => null);
          if (p) {
            if (!items.some((i) => i.product_id === p.id)) items.push({ product_id: p.id, slot: "other" });
            break;
          }
        }
      }
      if (items.length === 0) throw new Error("none");
      if (items.length === 1) return { product: items[0].product_id };
      const outfit = await outfits.create({ name: result.summary?.slice(0, 80) || "Found with a photo", items });
      return { outfit: outfit.id };
    },
    onSuccess: (r) => router.push("outfit" in r ? `/try?outfit=${r.outfit}` : `/try?product=${r.product}`),
    onError: () => setError("Couldn't put the look together. Try the items one by one."),
  });

  if (result.items.length === 0) {
    return (
      <div className="mx-auto mt-6 max-w-lg text-center">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={resolveMediaUrl(result.image_url)} alt="Your photo" className="mx-auto max-h-[360px] rounded-[20px] object-contain" />
        <p className="mt-5 text-[18px] font-semibold text-ink">We couldn&apos;t find clothes in this photo</p>
        <p className="mt-1 text-[15px] text-muted">Try a photo where the outfit is clear and not too small.</p>
        <button type="button" onClick={onAgain} className="tu-press mt-5 min-h-[48px] rounded-full bg-sage px-6 text-[15.5px] font-semibold text-white">
          Try another photo
        </button>
      </div>
    );
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
      <div className="lg:sticky lg:top-24 lg:self-start">
        <div className="relative mx-auto w-fit max-w-full overflow-hidden rounded-[22px] border border-line bg-paper-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={resolveMediaUrl(result.image_url)} alt="Your photo" className="block max-h-[70vh] w-auto max-w-full" />
          {result.items.map((it, i) => {
            const [x0, y0, x1, y1] = it.box;
            const on = i === active;
            return (
              <button
                key={i}
                type="button"
                onClick={() => setActive(i)}
                aria-label={`Show ${it.label}`}
                className={`absolute rounded-lg transition-[border-color,background-color] ${on ? "border-[2.5px] border-white bg-white/10 shadow-[0_0_0_2px_rgba(0,0,0,0.35)]" : "border border-white/0 hover:border-white/70"}`}
                style={{ left: `${x0 * 100}%`, top: `${y0 * 100}%`, width: `${(x1 - x0) * 100}%`, height: `${(y1 - y0) * 100}%` }}
              >
                <span
                  className={`absolute left-1/2 top-1/2 grid h-8 w-8 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full text-[14px] font-bold shadow-lift ${
                    on ? "bg-sage text-white" : "bg-white text-ink"
                  }`}
                >
                  {i + 1}
                </span>
              </button>
            );
          })}
        </div>
        <div className="mt-4 grid gap-2">
          <button
            type="button"
            onClick={() => wholeLook.mutate()}
            disabled={wholeLook.isPending}
            className="tu-press tu-attention min-h-[50px] rounded-full bg-sage px-5 text-[16px] font-semibold text-white hover:bg-sage-deep disabled:opacity-60"
          >
            {wholeLook.isPending ? "Putting it together…" : "Try the whole look on me"}
          </button>
          <button type="button" onClick={onAgain} className="min-h-[46px] rounded-full border border-line-strong text-[15px] font-semibold text-ink">
            Search another photo
          </button>
        </div>
      </div>

      <div className="min-w-0">
        {result.summary && <p className="text-[16px] text-ink-soft">{result.summary}</p>}
        <div className="mt-3 flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="Items found">
          {result.items.map((it, i) => (
            <button
              key={i}
              type="button"
              role="tab"
              aria-selected={i === active}
              onClick={() => setActive(i)}
              className={`flex min-h-[44px] shrink-0 items-center gap-2 rounded-full border px-3.5 text-[14.5px] font-semibold ${
                i === active ? "border-sage bg-sage text-white" : "border-line-strong bg-surface text-ink hover:border-sage"
              }`}
            >
              <span className={`grid h-6 w-6 place-items-center rounded-full text-[12.5px] ${i === active ? "bg-white/25" : "bg-paper-2"}`}>{i + 1}</span>
              {it.label}
            </button>
          ))}
        </div>

        {item && (
          <>
            <div className="mt-5 flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="font-display text-[26px] leading-tight text-ink">{item.label}</h2>
                <p className="text-[14.5px] text-muted">
                  {[item.color, item.details].filter(Boolean).join(" · ")}
                  {item.matches.length > 0 && ` · ${item.matches.length} products`}
                </p>
              </div>
              {item.matches.length > 1 && (
                <div className="flex rounded-full border border-line p-1" role="group" aria-label="Order">
                  {(
                    [
                      ["best", "Best match"],
                      ["price", "Lowest price"],
                    ] as const
                  ).map(([id, label]) => (
                    <button
                      key={id}
                      type="button"
                      onClick={() => setSort(id)}
                      aria-pressed={sort === id}
                      className={`min-h-[36px] rounded-full px-3.5 text-[14px] font-semibold ${sort === id ? "bg-ink text-surface" : "text-ink-soft"}`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              )}
            </div>
            {error && <p role="alert" className="mt-3 text-[14.5px] text-[#a4553f]">{error}</p>}
            {item.matches.length === 0 ? (
              <div className="mt-5 rounded-[20px] border border-dashed border-line p-8 text-center">
                <p className="text-[16px] text-muted">No shop has this right now.</p>
                <Link href="/stylist" className="mt-3 inline-block text-[15px] font-semibold text-sage-deep hover:underline">
                  Ask the AI Stylist for one like it →
                </Link>
              </div>
            ) : (
              <div className="mt-5 grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-3">
                {matches.map((m) => {
                  const key = `${m.product.retailer_slug}:${m.product.retailer_product_id}`;
                  return (
                    <ProductCard
                      key={key}
                      image={m.product.images[0]}
                      name={m.product.name}
                      priceCents={m.product.price_cents}
                      currency={m.product.currency}
                      shop={shopName(m.product.merchant_name, m.product.retailer_name)}
                      label={BADGE[m.match]}
                      badge={fromTryOnUStore(m.product.retailer_slug) ? RECOMMENDED : null}
                      busy={busyKey === key}
                      primary={{ label: "Try it on", onClick: () => act(m, "try"), disabled: !!busyKey }}
                      secondary={{ label: "View in shop ↗", onClick: () => act(m, "shop"), disabled: !!busyKey }}
                    />
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export function LensIcon({ size = 20 }: { size?: number }) {
  return (
    <svg className="shrink-0" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2" />
      <circle cx="12" cy="12" r="3.5" />
    </svg>
  );
}
