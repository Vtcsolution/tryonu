"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { VoiceInputButton } from "@/components/ui/VoiceInputButton";
import { MIN_PHOTOS, PhotoUploader } from "@/components/upload/PhotoUploader";
import { ApiError, affiliateGoUrl, resolveMediaUrl } from "@/lib/api/client";
import {
  liveSearch as liveSearchApi,
  outfits as outfitsApi,
  products as productsApi,
  savedLooks as savedLooksApi,
  stylist as stylistApi,
  tryon as tryonApi,
} from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";
import type { LiveProduct, Outfit, OutfitItem, Product, StylistResponse, TryOnJob, UserPhoto } from "@/lib/api/types";

// Slots FASHN can actually composite onto the photo (garments worn on the
// torso/legs) — shoes/watch/bag/accessory/other are still real matched
// products with their own shop-now link, just never visually applied.
const RENDERABLE_SLOTS = new Set(["top", "bottom", "dress", "outerwear"]);

const STEPS = ["Fitting profile", "Choose product", "Your look"] as const;
const TERMINAL: TryOnJob["status"][] = ["completed", "failed", "cancelled"];

const STAGE_LABEL: Record<TryOnJob["status"], string> = {
  queued: "Queued — waiting for a worker",
  processing: "Processing — rendering the look",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

export function TryFlow() {
  const router = useRouter();
  const params = useSearchParams();
  const preselectedProductId = params.get("product");
  const preselectedOutfitId = params.get("outfit");
  const { user, isLoading: sessionLoading } = useSession();
  const qc = useQueryClient();

  const [step, setStep] = useState(0);
  const [userPhotos, setUserPhotos] = useState<UserPhoto[]>([]);
  const [profileReady, setProfileReady] = useState(false);
  const [product, setProduct] = useState<Product | null>(null);
  const [outfit, setOutfit] = useState<Outfit | null>(null);
  const [prompt, setPrompt] = useState("");
  const [lastStylistReply, setLastStylistReply] = useState<StylistResponse | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);

  // gate the whole flow behind auth — a try-on always needs a stored photo
  useEffect(() => {
    if (!sessionLoading && !user) router.replace("/sign-in?next=/try");
  }, [sessionLoading, user, router]);

  const primaryPhoto =
    userPhotos.find((p) => p.kind === "front") ?? userPhotos.find((p) => p.kind === "full_body") ?? userPhotos[0];

  // The browse-grid is a live search against real retailer APIs, not our
  // own catalog — nothing here is a locally stored product until a user
  // actually picks one (see selectLive below).
  const [browseQuery, setBrowseQuery] = useState("");
  const liveSearchQuery = useQuery({
    queryKey: ["search", "live", browseQuery],
    queryFn: () => liveSearchApi.search(browseQuery.trim(), 12),
    enabled: step === 1 && browseQuery.trim().length > 1,
  });

  // The one place a browsed (not AI-picked) item becomes a real, saved
  // product — triggered by the user actually clicking it, not shown
  // speculatively for the whole results page.
  const selectLive = useMutation({
    mutationFn: (item: LiveProduct) =>
      productsApi.selectLive({
        query: browseQuery.trim(),
        retailer_slug: item.retailer_slug,
        retailer_product_id: item.retailer_product_id,
      }),
    onSuccess: (p) => {
      setProduct(p);
      setOutfit(null);
      setLastStylistReply(null);
    },
  });

  // "Shop" on an alternative (a real result the AI saw but didn't pick) —
  // persists it the same way selectLive does, then opens the real,
  // tracked affiliate link. Doesn't change the current try-on selection.
  const shopAlternative = useMutation({
    mutationFn: (item: LiveProduct) =>
      productsApi.selectLive({
        query: item.search_term ?? item.name,
        retailer_slug: item.retailer_slug,
        retailer_product_id: item.retailer_product_id,
      }),
    onSuccess: (p) => {
      window.open(affiliateGoUrl(p.id, "stylist"), "_blank", "noopener,noreferrer");
    },
  });

  // Deep-linked from the AI stylist or product search (?product=<id>) — pin
  // it into the picker's selection once we reach step 1, without changing
  // step-advancement logic for everyone else.
  const preselectedProductQuery = useQuery({
    queryKey: ["products", "preselected", preselectedProductId],
    queryFn: () => productsApi.get(preselectedProductId!),
    enabled: !!preselectedProductId && step === 1 && !product,
  });
  useEffect(() => {
    if (preselectedProductQuery.data && !product) setProduct(preselectedProductQuery.data);
  }, [preselectedProductQuery.data, product]);

  const preselectedOutfitQuery = useQuery({
    queryKey: ["outfits", "preselected", preselectedOutfitId],
    queryFn: () => outfitsApi.get(preselectedOutfitId!),
    enabled: !!preselectedOutfitId && step === 1 && !outfit,
  });
  useEffect(() => {
    if (preselectedOutfitQuery.data && !outfit) {
      setOutfit(preselectedOutfitQuery.data);
      setProduct(null);
    }
  }, [preselectedOutfitQuery.data, outfit]);

  // Free-text "apply Armani shirt, leopard shoes, a hat" — reuses the same
  // real-catalog-only AI stylist that powers /stylist, so this never
  // invents a product; it just picks real matches and (when more than one)
  // bundles them into an Outfit for the sequential multi-item try-on.
  const askStylist = useMutation({
    mutationFn: () => stylistApi.ask({ prompt: prompt.trim(), max_items: 6 }),
    onSuccess: (res) => {
      setLastStylistReply(res);
      if (res.outfit) {
        setOutfit(res.outfit);
        setProduct(null);
      } else if (res.products.length === 1) {
        setProduct(res.products[0]);
        setOutfit(null);
      } else {
        setProduct(null);
        setOutfit(null);
      }
    },
  });

  const createJob = useMutation({
    mutationFn: () =>
      tryonApi.create({
        user_photo_id: primaryPhoto!.id,
        product_id: outfit ? undefined : product!.id,
        outfit_id: outfit ? outfit.id : undefined,
      }),
    onSuccess: (job) => {
      setJobId(job.id);
      setElapsedSec(0);
      setStep(2);
      qc.invalidateQueries({ queryKey: ["session", "me"] }); // credits just changed
    },
  });

  const jobQuery = useQuery({
    queryKey: ["tryon-job", jobId],
    queryFn: () => tryonApi.get(jobId!),
    enabled: !!jobId && step === 2,
    refetchInterval: (query) => (query.state.data && TERMINAL.includes(query.state.data.status) ? false : 1200),
  });

  useEffect(() => {
    if (step !== 2 || !jobQuery.data || TERMINAL.includes(jobQuery.data.status)) return;
    const t = setInterval(() => setElapsedSec((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [step, jobQuery.data]);

  useEffect(() => {
    if (jobQuery.data?.status === "completed") {
      setStep(3);
      qc.invalidateQueries({ queryKey: ["session", "me"] });
    }
  }, [jobQuery.data?.status, qc]);

  const activeStepIndex = Math.min(step, 2);

  if (sessionLoading || !user) {
    return (
      <section className="mx-auto w-[min(920px,calc(100%-42px))] py-24 text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
        <p className="mt-4 text-[14px] text-muted">Checking your session…</p>
      </section>
    );
  }

  return (
    <section className="mx-auto w-[min(920px,calc(100%-42px))] py-14 md:py-20">
      {/* progress header */}
      <ol className="mb-10 flex items-center gap-3 text-[12px] sm:gap-4">
        {STEPS.map((label, i) => {
          const done = i < activeStepIndex || step === 3;
          const active = i === activeStepIndex && step !== 3;
          return (
            <li key={label} className="flex flex-1 items-center gap-3">
              <span
                className={`grid h-7 w-7 shrink-0 place-items-center rounded-full border text-[12px] font-semibold transition-colors duration-300 ${
                  done
                    ? "border-sage bg-sage text-white"
                    : active
                      ? "border-sage text-sage-deep"
                      : "border-line-strong text-faint"
                }`}
              >
                {done ? "✓" : i + 1}
              </span>
              <span
                className={`hidden font-display text-[14px] sm:block ${active || done ? "text-ink" : "text-faint"}`}
              >
                {label}
              </span>
              {i < STEPS.length - 1 && <span className="h-px flex-1 bg-line" />}
            </li>
          );
        })}
      </ol>

      {/* STEP 0 — upload */}
      {step === 0 && (
        <div key="s0" className="animate-[tu-in-right_0.4s_cubic-bezier(0.22,1,0.36,1)]">
          <h1 className="font-display text-[clamp(26px,4vw,40px)] leading-tight text-ink">
            Build your <em>fitting profile</em>
          </h1>
          <p className="mt-3 max-w-lg text-[15px] leading-relaxed text-muted">
            Add {MIN_PHOTOS}–10 clear photos for the best results. We reuse them for every
            try-on. Nothing is shared with retailers.
          </p>

          <div className="mt-8 rounded-[26px] border border-line bg-surface p-6 sm:p-8">
            <PhotoUploader
              onPhotosChange={(p, ready) => {
                setUserPhotos(p);
                setProfileReady(ready);
              }}
            />
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-4">
            <Button size="md" disabled={!profileReady} onClick={() => setStep(1)}>
              Continue <span aria-hidden="true">→</span>
            </Button>
            {!profileReady && (
              <span className="text-[13px] text-faint">
                Add at least a front or full-body photo to continue
              </span>
            )}
          </div>
        </div>
      )}

      {/* STEP 1 — pick a product */}
      {step === 1 && (
        <div key="s1" className="animate-[tu-in-right_0.4s_cubic-bezier(0.22,1,0.36,1)]">
          <h1 className="font-display text-[clamp(26px,4vw,40px)] leading-tight text-ink">
            Choose a <em>product</em>
          </h1>
          <p className="mt-3 max-w-lg text-[15px] leading-relaxed text-muted">
            Describe a look and our AI stylist will pull real matches from connected retailers —
            or browse the catalog below.
          </p>

          <form
            className="mt-6 flex flex-col gap-2 rounded-[22px] border border-line bg-surface p-3 sm:flex-row sm:items-center"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              if (!prompt.trim() || askStylist.isPending) return;
              askStylist.mutate();
            }}
          >
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. Armani shirt, leopard-print shoes, a black hat"
              className="h-11 flex-1 rounded-xl border border-line-strong bg-paper px-3.5 text-[14px] text-ink outline-none placeholder:text-faint focus:border-sage focus:ring-2 focus:ring-sage/25"
            />
            <VoiceInputButton
              onTranscript={(text) => setPrompt((p) => (p ? `${p} ${text}` : text))}
            />
            <Button type="submit" size="md" disabled={!prompt.trim() || askStylist.isPending}>
              {askStylist.isPending ? "Styling…" : "Style it"}
            </Button>
          </form>

          {askStylist.isError && (
            <p className="mt-3 text-[13px] text-[#a4553f]" role="alert">
              {askStylist.error instanceof ApiError
                ? askStylist.error.detail
                : "Couldn't reach the stylist. Please try again."}
            </p>
          )}

          {lastStylistReply && !outfit && !product && (
            <div className="mt-3 rounded-[18px] border border-dashed border-line p-4 text-[13px] text-muted">
              {lastStylistReply.summary || "No matching real products found for that — try a different prompt, or browse below."}
            </div>
          )}

          {(outfit || (product && lastStylistReply?.products.length === 1 && lastStylistReply.products[0].id === product.id)) && (
            <div className="mt-4 animate-[tu-in-scale_0.35s_ease] rounded-[20px] border border-sage bg-sage-tint/30 p-4">
              <div className="flex items-center justify-between">
                <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-sage-deep">
                  {outfit ? `AI-styled outfit · ${outfit.items.length} items` : "AI-styled pick"}
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setOutfit(null);
                    setProduct(null);
                    setLastStylistReply(null);
                  }}
                  className="text-[12px] text-faint underline-offset-2 hover:text-ink hover:underline"
                >
                  Clear
                </button>
              </div>

              {outfit ? (
                <>
                  <div className="mt-3 grid grid-cols-3 gap-2.5 sm:grid-cols-4">
                    {outfit.items.map((item) => (
                      <OutfitItemThumb key={item.id} item={item} />
                    ))}
                  </div>
                  <p className="mt-3 text-[12px] text-muted">
                    Clothing items are layered onto your photo; footwear/accessories are matched
                    products with their own shop link, shown alongside the result.
                  </p>
                  <div className="mt-4 space-y-3 border-t border-line/70 pt-3">
                    {outfit.items.map((item) => {
                      const alts = lastStylistReply?.alternatives[item.product.id] ?? [];
                      if (alts.length === 0) return null;
                      return (
                        <AlternativesRow
                          key={item.id}
                          label={item.product.name}
                          alternatives={alts}
                          onShop={(a) => shopAlternative.mutate(a)}
                          isShopping={shopAlternative.isPending}
                        />
                      );
                    })}
                  </div>
                </>
              ) : (
                product && (
                  <>
                    <div className="mt-3 flex items-center gap-3">
                      {(() => {
                        const thumb = resolveMediaUrl(product.images[0]?.url);
                        return thumb ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={thumb} alt={product.name} className="h-16 w-12 rounded-lg object-cover object-top" />
                        ) : null;
                      })()}
                      <div>
                        <p className="text-[13px] font-semibold text-ink">{product.name}</p>
                        <p className="text-[12px] text-muted">
                          {(product.price_cents / 100).toFixed(2)} {product.currency.toUpperCase()}
                        </p>
                      </div>
                    </div>
                    {(lastStylistReply?.alternatives[product.id] ?? []).length > 0 && (
                      <div className="mt-4 border-t border-line/70 pt-3">
                        <AlternativesRow
                          label={product.name}
                          alternatives={lastStylistReply!.alternatives[product.id]}
                          onShop={(a) => shopAlternative.mutate(a)}
                          isShopping={shopAlternative.isPending}
                        />
                      </div>
                    )}
                  </>
                )
              )}
            </div>
          )}

          <div className="mt-8 flex items-center gap-3 text-[12px] text-faint">
            <span className="h-px flex-1 bg-line" />
            or search for something specific
            <span className="h-px flex-1 bg-line" />
          </div>

          <input
            type="text"
            value={browseQuery}
            onChange={(e) => setBrowseQuery(e.target.value)}
            placeholder="e.g. blue denim jacket"
            className="mt-4 h-11 w-full rounded-xl border border-line-strong bg-paper px-3.5 text-[14px] text-ink outline-none placeholder:text-faint focus:border-sage focus:ring-2 focus:ring-sage/25"
          />
          <p className="mt-2 text-[11.5px] text-faint">
            Pulled live from connected retailers every time you search — nothing here is stored
            until you pick one.
          </p>

          <div className="mt-4">
            {liveSearchQuery.isFetching && (
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                {Array.from({ length: 8 }).map((_, i) => (
                  <div key={i} className="animate-pulse overflow-hidden rounded-[20px] border border-line">
                    <div className="aspect-[3/4] bg-paper-2" />
                    <div className="space-y-2 p-3">
                      <div className="h-3 w-3/4 rounded bg-paper-2" />
                      <div className="h-3 w-1/3 rounded bg-paper-2" />
                    </div>
                  </div>
                ))}
              </div>
            )}

            {liveSearchQuery.isError && (
              <div className="rounded-[20px] border border-line bg-surface p-8 text-center">
                <p className="text-[14px] text-muted">
                  {liveSearchQuery.error instanceof ApiError
                    ? liveSearchQuery.error.detail
                    : "Couldn't search right now."}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-4"
                  onClick={() => liveSearchQuery.refetch()}
                >
                  Retry
                </Button>
              </div>
            )}

            {!liveSearchQuery.isFetching && liveSearchQuery.data && liveSearchQuery.data.length === 0 && (
              <div className="rounded-[20px] border border-line bg-surface p-8 text-center text-[14px] text-muted">
                No real matches for that search — try different words.
              </div>
            )}

            {!liveSearchQuery.isFetching && liveSearchQuery.data && liveSearchQuery.data.length > 0 && (
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                {liveSearchQuery.data.map((item, i) => {
                  const selected =
                    product != null &&
                    !outfit &&
                    product.retailer.slug === item.retailer_slug &&
                    product.name === item.name;
                  const selecting =
                    selectLive.isPending &&
                    selectLive.variables?.retailer_product_id === item.retailer_product_id;
                  const thumb = resolveMediaUrl(item.images[0]);
                  return (
                    <div
                      key={`${item.retailer_slug}:${item.retailer_product_id}`}
                      style={{ animationDelay: `${i * 60}ms` }}
                      className="animate-[tu-in-scale_0.4s_ease_both]"
                    >
                      <button
                        type="button"
                        disabled={selectLive.isPending}
                        onClick={() => selectLive.mutate(item)}
                        className={`group tu-hover-card block w-full overflow-hidden rounded-[20px] border bg-surface text-left disabled:opacity-60 ${
                          selected ? "border-sage ring-2 ring-sage/40" : "border-line hover:border-line-strong"
                        }`}
                      >
                        <div className="relative aspect-[3/4] overflow-hidden bg-paper-2">
                          {thumb && (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                              src={thumb}
                              alt={item.name}
                              className="tu-hover-media h-full w-full object-cover object-top"
                            />
                          )}
                          <span className="absolute left-2 top-2 rounded-md bg-surface/95 px-2 py-1 text-[10px] font-semibold text-ink">
                            {item.merchant_name ? `${item.retailer_name} · ${item.merchant_name}` : item.retailer_name}
                          </span>
                          <span
                            className={`absolute right-2 top-2 grid h-6 w-6 transform-gpu place-items-center rounded-full text-[12px] text-white transition-[transform,opacity] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${
                              selecting
                                ? "scale-100 animate-spin rounded-full border-2 border-white/40 border-t-white bg-transparent opacity-100"
                                : selected
                                  ? "scale-100 bg-sage opacity-100"
                                  : "scale-50 bg-sage opacity-0"
                            }`}
                          >
                            {!selecting && "✓"}
                          </span>
                        </div>
                        <div className="p-3">
                          <p className="truncate text-[13px] font-semibold text-ink">{item.name}</p>
                          <p className="mt-0.5 text-[12px] text-muted">
                            {(item.price_cents / 100).toFixed(2)} {item.currency.toUpperCase()}
                          </p>
                        </div>
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {selectLive.isError && (
            <p className="mt-3 text-[13px] text-[#a4553f]" role="alert">
              {selectLive.error instanceof ApiError
                ? selectLive.error.detail
                : "Couldn't save that pick — it may no longer be available. Try again."}
            </p>
          )}

          {createJob.isError && (
            <p className="mt-4 text-[13px] text-[#a4553f]" role="alert">
              {createJob.error instanceof ApiError
                ? createJob.error.detail
                : "Couldn't start the try-on. Please try again."}
            </p>
          )}

          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Button
              size="md"
              disabled={(!product && !outfit) || createJob.isPending || selectLive.isPending}
              onClick={() => createJob.mutate()}
            >
              {createJob.isPending ? "Starting…" : "Generate try-on"}{" "}
              {!createJob.isPending && <span aria-hidden="true">→</span>}
            </Button>
            <button
              type="button"
              onClick={() => setStep(0)}
              className="font-display text-[14px] text-muted transition-colors hover:text-ink"
            >
              ← Back
            </button>
          </div>
        </div>
      )}

      {/* STEP 2 — processing */}
      {step === 2 && (
        <div key="s2" className="animate-[tu-in-scale_0.4s_cubic-bezier(0.22,1,0.36,1)]">
          <div className="rounded-[28px] border border-line bg-surface px-6 py-16 text-center">
            {jobQuery.data?.status !== "failed" ? (
              <div className="relative mx-auto grid h-24 w-24 place-items-center">
                <span className="absolute inset-0 rounded-full border-2 border-line" />
                <span className="absolute inset-0 animate-[tu-spin_0.9s_linear_infinite] rounded-full border-2 border-transparent border-t-sage" />
                <span className="absolute inset-2 animate-[tu-pulse-ring_1.8s_ease-out_infinite] rounded-full" />
                <span className="font-display text-[16px] text-ink">{elapsedSec}s</span>
              </div>
            ) : (
              <div className="mx-auto grid h-24 w-24 place-items-center rounded-full border-2 border-[#c0503a]/40 text-[28px]">
                ✕
              </div>
            )}

            <p className="mt-7 font-display text-[20px] text-ink">
              {jobQuery.data ? STAGE_LABEL[jobQuery.data.status] : "Starting…"}
            </p>
            <p className="mt-2 text-[13px] text-muted">
              {jobQuery.data?.status === "failed"
                ? jobQuery.data.error_message || "The AI provider couldn't complete this render. Your credits were refunded."
                : `Rendering ${outfit ? `your ${outfit.items.length}-item outfit` : (product?.name ?? "your look")} — this runs as a background job, so you could leave and come back.`}
            </p>

            {jobQuery.data?.status !== "failed" && (
              <div className="mx-auto mt-6 h-2 max-w-sm overflow-hidden rounded-full bg-paper-2">
                <div className="tu-flowline h-full w-full rounded-full opacity-70" />
              </div>
            )}

            <div className="mx-auto mt-5 flex max-w-sm flex-wrap items-center justify-center gap-2 text-[11px] text-faint">
              <span className="rounded-full border border-line px-2 py-1">
                job #{jobId?.slice(0, 8)}
              </span>
              <span className="rounded-full border border-line px-2 py-1">
                {jobQuery.data?.credit_cost ?? "—"} credit{jobQuery.data?.credit_cost === 1 ? "" : "s"} reserved
              </span>
              <span className="rounded-full border border-line px-2 py-1">refund on failure</span>
            </div>

            {jobQuery.data?.status === "failed" && (
              <div className="mt-6 flex justify-center gap-3">
                <Button
                  size="sm"
                  onClick={() => {
                    setProduct(null);
                    setOutfit(null);
                    setStep(1);
                  }}
                >
                  Try another product
                </Button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* STEP 3 — result */}
      {step === 3 &&
        jobQuery.data?.result &&
        (jobQuery.data.outfit ? (
          <OutfitResultStep
            job={jobQuery.data}
            outfit={jobQuery.data.outfit}
            onTryAnother={() => {
              setProduct(null);
              setOutfit(null);
              setJobId(null);
              setStep(1);
            }}
            onStartOver={() => {
              setProduct(null);
              setOutfit(null);
              setJobId(null);
              setStep(0);
            }}
          />
        ) : (
          (product || jobQuery.data.product) && (
            <ResultStep
              job={jobQuery.data}
              product={product || jobQuery.data.product!}
              onTryAnother={() => {
                setProduct(null);
                setOutfit(null);
                setJobId(null);
                setStep(1);
              }}
              onStartOver={() => {
                setProduct(null);
                setOutfit(null);
                setJobId(null);
                setStep(0);
              }}
            />
          )
        ))}
    </section>
  );
}

function ResultStep({
  job,
  product,
  onTryAnother,
  onStartOver,
}: {
  job: TryOnJob;
  product: Product;
  onTryAnother: () => void;
  onStartOver: () => void;
}) {
  return (
    <div key="s3" className="animate-[tu-in-scale_0.45s_cubic-bezier(0.22,1,0.36,1)]">
      <div className="flex items-center gap-2">
        <span className="grid h-6 w-6 place-items-center rounded-full bg-sage text-[12px] text-white">✓</span>
        <h1 className="font-display text-[clamp(24px,3.6vw,36px)] leading-tight text-ink">
          Here&rsquo;s <em>you</em>, in {product.name}
        </h1>
      </div>

      <div className="mt-6 grid gap-6 md:grid-cols-[1.4fr_1fr]">
        <div className="relative aspect-[4/5] overflow-hidden rounded-[26px] border border-line shadow-lift md:aspect-auto md:min-h-[460px]">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={resolveMediaUrl(job.result!.image_url)}
            alt={`AI try-on result — ${product.name}`}
            className="h-full w-full object-cover object-top"
          />
          <span className="absolute right-4 top-4 rounded-full bg-sage px-3 py-1.5 text-[11px] font-semibold text-white">
            AI try-on result
          </span>
          <p className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/55 to-transparent px-4 pb-3 pt-8 text-[11.5px] leading-snug text-white/90">
            AI-generated visualization — not a guarantee of exact fit, sizing, or color.
          </p>
        </div>

        <div className="flex flex-col rounded-[26px] border border-line bg-surface p-6">
          <p className="text-[11px] uppercase tracking-[0.14em] text-faint">
            {product.merchant_name ? `${product.retailer.name} · ${product.merchant_name}` : product.retailer.name}
          </p>
          <p className="mt-1 font-display text-[22px] text-ink">{product.name}</p>
          <p className="mt-1 text-[15px] text-muted">
            {(product.price_cents / 100).toFixed(2)} {product.currency.toUpperCase()}
          </p>

          <div className="mt-5 space-y-2 text-[13px] text-muted">
            <p className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-sage" /> {job.credit_cost} credit
              {job.credit_cost === 1 ? "" : "s"} used · job completed
            </p>
            <p className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-sage" /> Rendered by {job.provider}
            </p>
          </div>

          <div className="mt-auto space-y-3 pt-6">
            <Button href={affiliateGoUrl(product.id, "tryon_result")} size="md" className="w-full">
              Shop now <span aria-hidden="true">→</span>
            </Button>
            <SaveLookButton tryonResultId={job.result!.id} />
            <Button variant="outline" size="md" className="w-full" onClick={onTryAnother}>
              Try another product
            </Button>
            <button
              type="button"
              onClick={onStartOver}
              className="w-full text-center font-display text-[13px] text-muted transition-colors hover:text-ink"
            >
              Start over
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function OutfitItemThumb({ item }: { item: OutfitItem }) {
  const thumb = resolveMediaUrl(item.product.images[0]?.url);
  const rendered = RENDERABLE_SLOTS.has(item.slot);
  return (
    <div className="overflow-hidden rounded-[14px] border border-line bg-surface">
      <div className="relative aspect-square bg-paper-2">
        {thumb && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={thumb} alt={item.product.name} className="h-full w-full object-cover object-top" />
        )}
        <span
          className={`absolute bottom-1 left-1 rounded-full px-1.5 py-0.5 text-[9px] font-semibold ${
            rendered ? "bg-sage text-white" : "bg-surface/95 text-ink-soft"
          }`}
        >
          {rendered ? "on photo" : "matched"}
        </span>
      </div>
      <p className="truncate px-1.5 py-1 text-[10.5px] text-ink-soft">{item.product.name}</p>
    </div>
  );
}

function AlternativesRow({
  label,
  alternatives,
  onShop,
  isShopping,
}: {
  label: string;
  alternatives: LiveProduct[];
  onShop: (item: LiveProduct) => void;
  isShopping: boolean;
}) {
  return (
    <div>
      <p className="truncate text-[11px] text-faint">Other options for &ldquo;{label}&rdquo;</p>
      <div className="mt-1.5 flex gap-2 overflow-x-auto pb-1">
        {alternatives.map((alt) => {
          const thumb = resolveMediaUrl(alt.images[0]);
          return (
            <button
              key={`${alt.retailer_slug}:${alt.retailer_product_id}`}
              type="button"
              disabled={isShopping}
              onClick={() => onShop(alt)}
              title={`${alt.name} — ${(alt.price_cents / 100).toFixed(2)} ${alt.currency.toUpperCase()}`}
              className="flex w-20 shrink-0 flex-col overflow-hidden rounded-[12px] border border-line bg-surface text-left transition-colors hover:border-sage disabled:opacity-60"
            >
              <div className="relative aspect-square bg-paper-2">
                {thumb && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={thumb} alt={alt.name} className="h-full w-full object-cover object-top" />
                )}
              </div>
              <p className="px-1 py-1 text-[10px] font-semibold text-ink-soft">
                {(alt.price_cents / 100).toFixed(0)} {alt.currency.toUpperCase()}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function OutfitResultStep({
  job,
  outfit,
  onTryAnother,
  onStartOver,
}: {
  job: TryOnJob;
  outfit: Outfit;
  onTryAnother: () => void;
  onStartOver: () => void;
}) {
  const renderedCount = outfit.items.filter((i) => RENDERABLE_SLOTS.has(i.slot)).length;

  return (
    <div key="s3-outfit" className="animate-[tu-in-scale_0.45s_cubic-bezier(0.22,1,0.36,1)]">
      <div className="flex items-center gap-2">
        <span className="grid h-6 w-6 place-items-center rounded-full bg-sage text-[12px] text-white">✓</span>
        <h1 className="font-display text-[clamp(24px,3.6vw,36px)] leading-tight text-ink">
          Here&rsquo;s <em>you</em>, styled
        </h1>
      </div>

      <div className="mt-6 grid gap-6 md:grid-cols-[1.4fr_1fr]">
        <div className="relative aspect-[4/5] overflow-hidden rounded-[26px] border border-line shadow-lift md:aspect-auto md:min-h-[460px]">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={resolveMediaUrl(job.result!.image_url)}
            alt="AI try-on result — styled outfit"
            className="h-full w-full object-cover object-top"
          />
          <span className="absolute right-4 top-4 rounded-full bg-sage px-3 py-1.5 text-[11px] font-semibold text-white">
            AI try-on result
          </span>
          <p className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/55 to-transparent px-4 pb-3 pt-8 text-[11.5px] leading-snug text-white/90">
            {renderedCount} of {outfit.items.length} items applied to the photo — footwear/accessories
            are matched products, not visually composited.
          </p>
        </div>

        <div className="flex flex-col rounded-[26px] border border-line bg-surface p-6">
          <p className="text-[11px] uppercase tracking-[0.14em] text-faint">
            {outfit.items.length}-item outfit · {(outfit.total_price_cents / 100).toFixed(2)}
          </p>
          {outfit.compatibility_score != null && (
            <p className="mt-1 text-[13px] text-muted">{outfit.compatibility_score}% style match</p>
          )}

          <div className="mt-4 grid grid-cols-3 gap-2">
            {outfit.items.map((item) => (
              <OutfitItemThumb key={item.id} item={item} />
            ))}
          </div>

          <div className="mt-5 space-y-1.5 border-t border-line pt-4">
            {outfit.items.map((item) => (
              <div key={item.id} className="flex items-center justify-between gap-2 text-[12.5px]">
                <span className="truncate text-ink-soft">{item.product.name}</span>
                <Button
                  href={affiliateGoUrl(item.product.id, "tryon_result")}
                  size="sm"
                  variant="outline"
                  className="!h-7 shrink-0 !px-2.5 !text-[11px]"
                >
                  Shop now
                </Button>
              </div>
            ))}
          </div>

          <div className="mt-5 space-y-2 text-[13px] text-muted">
            <p className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-sage" /> {job.credit_cost} credit
              {job.credit_cost === 1 ? "" : "s"} used · job completed
            </p>
            <p className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-sage" /> Rendered by {job.provider}
            </p>
          </div>

          <div className="mt-auto space-y-3 pt-6">
            <SaveLookButton tryonResultId={job.result!.id} />
            <Button variant="outline" size="md" className="w-full" onClick={onTryAnother}>
              Try another look
            </Button>
            <button
              type="button"
              onClick={onStartOver}
              className="w-full text-center font-display text-[13px] text-muted transition-colors hover:text-ink"
            >
              Start over
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function SaveLookButton({ tryonResultId }: { tryonResultId: string }) {
  const save = useMutation({ mutationFn: () => savedLooksApi.save(tryonResultId) });

  if (save.isSuccess) {
    return (
      <Button variant="outline" size="md" className="w-full" disabled>
        Saved to your lookbook ✓
      </Button>
    );
  }

  return (
    <Button
      variant="outline"
      size="md"
      className="w-full"
      disabled={save.isPending}
      onClick={() => save.mutate()}
    >
      {save.isPending ? "Saving…" : "Save this look"}
    </Button>
  );
}
