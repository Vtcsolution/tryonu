"use client";

import { CheckIcon, XIcon } from "@/components/ui/Icons";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { VoiceInputButton } from "@/components/ui/VoiceInputButton";
import { ZoomableImage } from "@/components/try/ZoomableImage";
import { LookBoard } from "@/components/try/LookBoard";
import { markerNumber } from "@/components/try/ResultMarkers";
import { PhotoUploader } from "@/components/upload/PhotoUploader";
import { ApiError, affiliateGoUrl, resolveMediaUrl } from "@/lib/api/client";
import { StyledPicks } from "@/components/try/StyledPicks";
import { ProductCard } from "@/components/product/ProductCard";
import { ShareLook } from "@/components/try/ShareLook";
import { PriceAlertButton } from "@/components/alerts/PriceAlerts";
import { WhatsAppOrderButton } from "@/components/whatsapp/WhatsApp";
import { LensIcon } from "@/components/lens/LensIcon";
import { YourSize } from "@/components/size/MySize";
import { PostToCommunity } from "@/components/community/PostToCommunity";
import { FEATURED, RECOMMENDED, RetailerTag, fromTryOnUStore, retailerFromImage, shopName } from "@/components/try/shop";
import {
  credits as creditsApi,
  liveSearch as liveSearchApi,
  outfits as outfitsApi,
  preferences as preferencesApi,
  products as productsApi,
  savedLooks as savedLooksApi,
  stylist as stylistApi,
  tryon as tryonApi,
  wardrobe as wardrobeApi,
} from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";
import type {
  DistractorOption,
  LiveProduct,
  Outfit,
  OutfitItem,
  OutfitSlot,
  PhotoKind,
  Product,
  ResultPlacement,
  StylistResponse,
  TryOnJob,
  UserPhoto,
  WardrobeItem,
} from "@/lib/api/types";

// Slots FASHN's tryon-max model can composite onto the photo — watch/bag/
// accessory/other are still real matched products with their own shop-now
// link, just never visually applied. Must match the backend's
// _renderable_slots("tryon-max") in app/workers/tasks/tryon_tasks.py.
// Tap-to-ask starters under the stylist box, matched to the shopper's gender preference
// short on purpose: the server fills in the whole look ("Pink bridal look" =
// lehenga, dupatta, jewellery, khussa, clutch; see _ready_look in stylist_service.py)
const WOMEN_PROMPTS = ["Pink bridal look", "Red bridal look", "Mehndi look", "Eid outfit", "Party look", "Office look", "Casual look"];
const MEN_PROMPTS = ["Groom look", "Eid outfit for men", "Party look for men", "Office look for men", "Casual look for men"];


const STEPS = ["Your photo", "Choose product", "Your look"] as const;
const TERMINAL: TryOnJob["status"][] = ["completed", "failed", "cancelled"];
// the try-on still running when the shopper left /try, opened again when they come back
const RUNNING_KEY = "tu_running_tryon";
const RESUME_HOURS = 3;
// past this, the wait screen says so plainly
const LONG_WAIT_SEC = 300;

const clock = (sec: number) => (sec < 60 ? `${sec}s` : `${Math.floor(sec / 60)}m ${String(sec % 60).padStart(2, "0")}s`);

const STAGE_LABEL: Record<TryOnJob["status"], string> = {
  queued: "Queued — your render starts when a worker is free",
  processing: "Processing — rendering the look",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

// Human labels for the multi-angle result gallery — not every kind is a
// realistic "second angle" pick, but the map covers everything PhotoUploader
// can produce.
const PHOTO_KIND_LABEL: Record<PhotoKind, string> = {
  front: "Front view",
  full_body: "Full body",
  left_side: "Left side",
  right_side: "Right side",
  left_45: "Left 45°",
  right_45: "Right 45°",
  back: "Back view",
  extra: "Extra angle",
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
  const [customItem, setCustomItem] = useState<WardrobeItem | null>(null);
  const [prompt, setPrompt] = useState("");
  const prefQuery = useQuery({ queryKey: ["preferences"], queryFn: preferencesApi.get, enabled: !!user });
  const gender = prefQuery.data?.gender;
  const suggestionsQuery = useQuery({
    queryKey: ["stylist", "suggestions"],
    queryFn: stylistApi.suggestions,
    enabled: !!user,
  });
  const personalPrompts = suggestionsQuery.data?.prompts ?? [];
  // short ready looks first, then two built from the styles they picked
  const readyLooks =
    gender === "men" ? MEN_PROMPTS : gender === "women" ? WOMEN_PROMPTS : [...WOMEN_PROMPTS.slice(0, 4), ...MEN_PROMPTS.slice(0, 2)];
  const starterPrompts = [...readyLooks, ...personalPrompts.slice(0, 2)];
  const [lastStylistReply, setLastStylistReply] = useState<StylistResponse | null>(null);
  // after "Try on" swaps an alternative in: which item to highlight, and what to restore on Undo
  const [swappedInId, setSwappedInId] = useState<string | null>(null);
  const [beforeSwap, setBeforeSwap] = useState<{ product: Product | null; outfit: Outfit | null; reply: StylistResponse | null } | null>(null);
  const pickRef = useRef<HTMLDivElement>(null);
  const [jobIds, setJobIds] = useState<string[]>([]);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [multiAngle, setMultiAngle] = useState(false);
  // "Add more to this look": the finished look the next try-on adds onto
  const [baseLook, setBaseLook] = useState<TryOnJob | null>(null);
  const [addMenuOpen, setAddMenuOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // gate the whole flow behind auth — a try-on always needs a stored photo
  useEffect(() => {
    // keep ?outfit= / ?product= (a shared look being tried on) through sign-in
    if (!sessionLoading && !user)
      router.replace(`/sign-in?next=${encodeURIComponent(`/try${window.location.search}`)}`);
  }, [sessionLoading, user, router]);

  const primaryPhoto =
    userPhotos.find((p) => p.kind === "front") ?? userPhotos.find((p) => p.kind === "full_body") ?? userPhotos[0];
  // A second angle to render alongside the primary one — prefer an explicit
  // back photo (the common "front + back" case), else any other distinct
  // uploaded angle.
  const secondaryPhoto = userPhotos.find((p) => p.kind === "back" && p.id !== primaryPhoto?.id)
    ?? userPhotos.find((p) => p.id !== primaryPhoto?.id);
  const canMultiAngle = !!primaryPhoto && !!secondaryPhoto;

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
      setCustomItem(null);
      setLastStylistReply(null);
    },
  });

  // "Upload your own item" — the user's own photo of something they
  // already own, never a shoppable catalog Product. Two-step against the
  // existing wardrobe API: create the item, then attach the photo.
  const wardrobeQuery = useQuery({
    queryKey: ["wardrobe"],
    queryFn: wardrobeApi.list,
    enabled: step === 1,
  });
  const uploadCustomItem = useMutation({
    mutationFn: async (file: File) => {
      const item = await wardrobeApi.create({ name: file.name.replace(/\.[^/.]+$/, "").slice(0, 80) || "My item" });
      return wardrobeApi.uploadPhoto(item.id, file);
    },
    onSuccess: (item) => {
      setCustomItem(item);
      setProduct(null);
      setOutfit(null);
      setLastStylistReply(null);
      qc.invalidateQueries({ queryKey: ["wardrobe"] });
    },
  });

  const saveLive = (item: LiveProduct) =>
    productsApi.selectLive({
      query: item.search_term ?? item.name,
      retailer_slug: item.retailer_slug,
      retailer_product_id: item.retailer_product_id,
    });

  // "Buy" on an alternative: persists it, then opens the tracked store link.
  // Doesn't change the current try-on selection.
  const shopAlternative = useMutation({ mutationFn: saveLive });
  const buyAlternative = (item: LiveProduct) => {
    // opened synchronously so popup blockers allow it, then pointed at the link
    const tab = window.open("", "_blank");
    shopAlternative.mutate(item, {
      onSuccess: (p) => {
        const url = affiliateGoUrl(p.id, "stylist");
        if (tab) {
          tab.opener = null;
          tab.location.href = url;
        } else {
          window.location.href = url;
        }
      },
      onError: () => tab?.close(),
    });
  };

  // "Try on" on an alternative: swaps it in for the item it's an
  // alternative to — a new outfit with the same slots when an outfit is
  // selected (try-ons render a saved outfit), or the single pick otherwise.
  const applyAlternative = useMutation({
    mutationFn: async ({ alt, replaceId }: { alt: LiveProduct; replaceId: string }) => {
      const picked = await saveLive(alt);
      if (!outfit) return { picked, newOutfit: null };
      const newOutfit = await outfitsApi.create({
        name: outfit.name ?? undefined,
        occasion: outfit.occasion ?? undefined,
        items: outfit.items.map((it) => ({
          product_id: it.product.id === replaceId ? picked.id : it.product.id,
          slot: it.slot as OutfitSlot,
        })),
      });
      return { picked, newOutfit };
    },
    onSuccess: ({ picked, newOutfit }, { alt, replaceId }) => {
      setBeforeSwap({ product, outfit, reply: lastStylistReply });
      // the other options stay available for the swapped-in item, minus the one just chosen
      setLastStylistReply((prev) => {
        if (!prev) return prev;
        const { [replaceId]: options = [], ...rest } = prev.alternatives;
        return {
          ...prev,
          products: prev.products.map((p) => (p.id === replaceId ? picked : p)),
          alternatives: {
            ...rest,
            [picked.id]: options.filter((o) => o.retailer_product_id !== alt.retailer_product_id),
          },
        };
      });
      if (newOutfit) setOutfit(newOutfit);
      else setProduct(picked);
      setSwappedInId(picked.id);
      pickRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    },
  });

  const undoSwap = () => {
    if (!beforeSwap) return;
    setProduct(beforeSwap.product);
    setOutfit(beforeSwap.outfit);
    setLastStylistReply(beforeSwap.reply);
    setBeforeSwap(null);
    setSwappedInId(null);
  };

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
  //
  // The server lowers max_items to the most products one look applies
  // (Admin → "Most products in one look", TRYON_DIRECT_MAX_PRODUCTS); only
  // that many things named are searched and the reply says which were left out.
  const askStylist = useMutation({
    mutationFn: (text: string) => stylistApi.ask({ prompt: text.trim(), max_items: 10 }),
    onSuccess: (res) => {
      setLastStylistReply(res);
      setCustomItem(null);
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

  // "Buy credits" comes back here afterwards, with the same products selected
  const buyHref = `/credits?next=${encodeURIComponent(
    outfit ? `/try?outfit=${outfit.id}` : product ? `/try?product=${product.id}` : "/try",
  )}`;

  // a TryOnU store paying for this try-on (the shopper chooses: free and shared, or private)
  const sponsorTarget = !customItem && !(multiAngle && canMultiAngle) ? (outfit ? { outfit_id: outfit.id } : product ? { product_id: product.id } : null) : null;
  const sponsorQuery = useQuery({
    queryKey: ["tryon-sponsor", sponsorTarget?.outfit_id ?? null, sponsorTarget?.product_id ?? null],
    queryFn: () => tryonApi.sponsor(sponsorTarget!),
    enabled: !!user && !!sponsorTarget,
    staleTime: 30_000,
  });
  const sponsorName = sponsorTarget ? sponsorQuery.data?.store_name ?? null : null;

  const createJob = useMutation({
    mutationFn: async (useStoreCredit: boolean) => {
      const sponsored = useStoreCredit ? { use_store_credit: true } : {};
      const target = customItem
        ? { wardrobe_item_id: customItem.id }
        : outfit
          ? { outfit_id: outfit.id }
          : { product_id: product!.id };
      // The real "other options" the shopper saw next to each selected
      // item, if the ask-stylist flow is what put it there — the live
      // distractor set for the backend's shadow-mode identity check,
      // used in preference to its own same-category guess. A live
      // alternative has no id of its own until it's actually selected
      // (see LiveProduct's own comment), so product_id goes through as
      // null and only its photo is sent.
      const alternatives = lastStylistReply?.alternatives;
      const distractor_options: Record<string, DistractorOption[]> | undefined = alternatives
        ? Object.fromEntries(
            Object.entries(alternatives)
              .map(([productId, options]) => [
                productId,
                options.filter((o) => o.images[0]).map((o) => ({ product_id: null, image_url: o.images[0] })),
              ] as const)
              .filter(([, options]) => options.length > 0)
          )
        : undefined;
      const withDistractors = distractor_options && Object.keys(distractor_options).length
        ? { distractor_options }
        : {};
      if (baseLook) {
        // a further round: same photo as the look, drawn onto its finished image
        const job = await tryonApi.create({
          user_photo_id: baseLook.user_photo.id,
          ...target,
          ...withDistractors,
          ...sponsored,
          base_job_id: baseLook.id,
        });
        return [job];
      }
      if (multiAngle && canMultiAngle) {
        return tryonApi.createMulti({
          user_photo_ids: [primaryPhoto!.id, secondaryPhoto!.id],
          ...target,
          ...withDistractors,
        });
      }
      const job = await tryonApi.create({ user_photo_id: primaryPhoto!.id, ...target, ...withDistractors, ...sponsored });
      return [job];
    },
    onSuccess: (jobs) => {
      setJobIds(jobs.map((j) => j.id));
      remember(jobs.map((j) => j.id));
      setElapsedSec(0);
      setStep(2);
      qc.invalidateQueries({ queryKey: ["session", "me"] }); // credits just changed
    },
    // the store's free try-ons may have just run out: ask again
    onError: () => qc.invalidateQueries({ queryKey: ["tryon-sponsor"] }),
  });

  const jobQueries = useQueries({
    queries: jobIds.map((id) => ({
      queryKey: ["tryon-job", id],
      queryFn: () => tryonApi.get(id),
      enabled: !!id,
      refetchInterval: (query: { state: { data?: TryOnJob } }) =>
        query.state.data && TERMINAL.includes(query.state.data.status) ? false : 1200,
    })),
  });
  const jobsData = jobQueries.map((q) => q.data).filter((j): j is TryOnJob => !!j);
  const allTerminal = jobIds.length > 0 && jobsData.length === jobIds.length && jobsData.every((j) => TERMINAL.includes(j.status));
  const anyCompleted = jobsData.some((j) => j.status === "completed");
  const completedJobs = jobsData.filter((j) => j.status === "completed");

  // counted from when the try-on was really made, so it stays right after leaving and coming back
  const made = jobsData[0]?.created_at;
  // the server's times are UTC; one written without its zone would read as local time
  const madeAt = made ? Date.parse(/[zZ]|[+-]\d\d:?\d\d$/.test(made) ? made : `${made}Z`) : NaN;
  useEffect(() => {
    if (step !== 2 || jobsData.length === 0 || allTerminal) return;
    const tick = () =>
      setElapsedSec((s) => (Number.isFinite(madeAt) ? Math.max(0, Math.round((Date.now() - madeAt) / 1000)) : s + 1));
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [step, jobsData.length, allTerminal, madeAt]);

  // Leaving the page used to lose the try-on ("you can leave and come back" wasn't true):
  // the running one is remembered and opened again, or the one a link names (?job=)
  const resumeJobId = params.get("job");
  const resumed = useRef(false);
  useEffect(() => {
    if (!user || resumed.current) return;
    resumed.current = true;
    let ids = resumeJobId ? [resumeJobId] : [];
    // a product or look opened on purpose comes first
    if (ids.length === 0 && !preselectedProductId && !preselectedOutfitId) {
      try {
        const saved = JSON.parse(localStorage.getItem(RUNNING_KEY) || "null") as { ids: string[]; at: number; user: string } | null;
        if (saved && saved.user === user.id && Date.now() - saved.at < RESUME_HOURS * 3_600_000) ids = saved.ids;
      } catch {
        // nothing remembered
      }
    }
    if (ids.length > 0) {
      setJobIds(ids);
      setStep(2);
    }
  }, [user, resumeJobId, preselectedProductId, preselectedOutfitId]);
  const remember = (ids: string[]) => {
    try {
      localStorage.setItem(RUNNING_KEY, JSON.stringify({ ids, at: Date.now(), user: user?.id }));
    } catch {
      // storage blocked: the try-on still runs, it just isn't reopened
    }
  };
  useEffect(() => {
    // finished, and shown now: nothing to reopen
    if (!allTerminal) return;
    try {
      localStorage.removeItem(RUNNING_KEY);
    } catch {
      // nothing to forget
    }
  }, [allTerminal]);

  useEffect(() => {
    if (step === 2 && allTerminal && anyCompleted) {
      setStep(3);
      qc.invalidateQueries({ queryKey: ["session", "me"] });
    }
  }, [step, allTerminal, anyCompleted, qc]);

  const activeStepIndex = Math.min(step, 2);

  // what this try-on will cost, against the shopper's balance
  const pricingQuery = useQuery({ queryKey: ["credit-pricing"], queryFn: creditsApi.pricing, staleTime: 60_000 });
  const tryOnCost = pricingQuery.data
    ? (outfit || baseLook ? pricingQuery.data.outfit_tryon_cost : pricingQuery.data.tryon_cost) *
      (multiAngle && canMultiAngle && !baseLook ? 2 : 1)
    : null;
  const balance = user?.credits_balance ?? 0;
  const shortOfCredits = tryOnCost !== null && balance < tryOnCost;

  const addMoreTo = (job: TryOnJob) => {
    setBaseLook(job);
    // a fresh ask for this round: the last round's prompt and stylist reply
    // left in place read as if this round were already done
    setPrompt("");
    setLastStylistReply(null);
    setBrowseQuery("");
    setProduct(null);
    setOutfit(null);
    setCustomItem(null);
    setJobIds([]);
    setMultiAngle(false);
    setStep(1);
  };

  if (sessionLoading || !user) {
    return (
      <section className="tu-container py-24 text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
        <p className="mt-4 text-[15px] text-muted">Checking your session…</p>
      </section>
    );
  }

  return (
    <section className="tu-container pb-10 pt-4 lg:py-20">
      {/* progress header */}
      <ol className="flex w-full items-center gap-3 text-[13px] sm:gap-4">
        {STEPS.map((label, i) => {
          const done = i < activeStepIndex || step === 3;
          const active = i === activeStepIndex && step !== 3;
          return (
            // the last step only takes its own width, so the row spans edge to edge
            <li key={label} className={`flex items-center gap-3 ${i < STEPS.length - 1 ? "flex-1" : "flex-none"}`}>
              <span
                className={`grid h-7 w-7 shrink-0 place-items-center rounded-full border text-[13px] font-semibold transition-colors duration-300 ${
                  done
                    ? "border-sage bg-sage text-white"
                    : active
                      ? "border-sage text-sage-deep"
                      : "border-line-strong text-faint"
                }`}
              >
                {done ? <CheckIcon size={14} /> : i + 1}
              </span>
              <span
                className={`hidden font-display text-[15px] sm:block ${active || done ? "text-ink" : "text-faint"}`}
              >
                {label}
              </span>
              {i < STEPS.length - 1 && <span className="h-px flex-1 bg-line" />}
            </li>
          );
        })}
      </ol>
      <p className="mb-5 mt-3 text-[14px] text-muted sm:hidden">
        Step {Math.min(activeStepIndex, 2) + 1} of {STEPS.length} · <span className="text-ink">{STEPS[Math.min(activeStepIndex, 2)]}</span>
      </p>
      <div className="mb-10 hidden sm:block" />

      {/* STEP 0 — upload */}
      {step === 0 && (
        <div key="s0" className="animate-[tu-in-right_0.4s_cubic-bezier(0.22,1,0.36,1)]">
          <h1 className="font-display text-[24px] leading-tight text-ink lg:text-[clamp(26px,4vw,40px)]">
            {/* phones: say it in plain words */}
            <span className="lg:hidden">Add your photo</span>
            <span className="max-lg:hidden">
              Add your <em>photo</em>
            </span>
          </h1>
          <p className="mt-2 max-w-lg text-[15px] leading-relaxed text-muted lg:mt-3 lg:text-[16px]">
            <span className="lg:hidden">One clear, full-length photo of you. We use it for every try-on and never share it.</span>
            <span className="max-lg:hidden">
              A clear front photo is all you need — add back and side photos for even better results. We reuse them for every
              try-on. Nothing is shared with retailers.
            </span>
          </p>

          <div className="mt-5 lg:mt-8 lg:rounded-[26px] lg:border lg:border-line lg:bg-surface lg:p-8">
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
              <span className="text-[14px] text-faint">
                Add at least a front or full-body photo to continue
              </span>
            )}
          </div>
        </div>
      )}

      {/* STEP 1 — pick a product */}
      {step === 1 && (
        <div key="s1" className="animate-[tu-in-right_0.4s_cubic-bezier(0.22,1,0.36,1)]">
          {baseLook && (
            <div className="mb-5 flex flex-wrap items-center gap-3 rounded-[18px] border border-sage/40 bg-sage/10 p-3">
              {baseLook.result && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={resolveMediaUrl(baseLook.result.image_url)}
                  alt="Your look so far"
                  className="h-16 w-12 shrink-0 rounded-[10px] object-cover object-top"
                />
              )}
              <p className="min-w-0 flex-1 text-[14px] leading-snug text-ink-soft">
                Adding to your look · round {baseLook.look_round + 1} of {baseLook.max_look_rounds}.
                Choose up to 5 more products; they&rsquo;re drawn onto your finished image, and a new item of
                the same kind (earrings, a watch, a dress) replaces the one you have.
              </p>
              <button
                type="button"
                onClick={() => setBaseLook(null)}
                className="shrink-0 text-[13px] font-medium text-muted underline-offset-2 hover:text-ink hover:underline"
              >
                Start a new look instead
              </button>
            </div>
          )}
          <h1 className="font-display text-[clamp(26px,4vw,40px)] leading-tight text-ink">
            Choose a <em>product</em>
          </h1>
          <p className="mt-3 max-w-lg text-[16px] leading-relaxed text-muted">
            Describe a look and our AI stylist will pull real matches from connected retailers,
            upload something you already own to try it on, or browse the catalog below.
          </p>

          <div className="mt-6 flex flex-col gap-2 rounded-[26px] border border-line bg-surface p-2 sm:flex-row sm:items-center">
            <div className="relative shrink-0">
              <button
                type="button"
                onClick={() => setAddMenuOpen((o) => !o)}
                aria-label="Add your own item"
                aria-expanded={addMenuOpen}
                className={`grid h-11 w-11 place-items-center rounded-full border text-[20px] leading-none transition-colors ${
                  addMenuOpen
                    ? "border-sage bg-sage text-white"
                    : "border-line-strong text-ink-soft hover:border-sage hover:text-sage-deep"
                }`}
              >
                +
              </button>

              {addMenuOpen && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setAddMenuOpen(false)} />
                  <div className="absolute left-0 top-full z-20 mt-2 w-[280px] overflow-hidden rounded-[18px] border border-line bg-surface p-1.5 shadow-lift">
                    <button
                      type="button"
                      onClick={() => {
                        setAddMenuOpen(false);
                        fileInputRef.current?.click();
                      }}
                      className="flex w-full items-start gap-3 rounded-[12px] px-3 py-2.5 text-left transition-colors hover:bg-paper-2"
                    >
                                            <span>
                        <span className="block text-[14.5px] font-semibold text-ink">Upload your own item</span>
                        <span className="block text-[13px] text-faint">
                          Try on a photo of something you already own
                        </span>
                      </span>
                    </button>

                    {wardrobeQuery.data && wardrobeQuery.data.filter((w) => w.image_url).length > 0 && (
                      <div className="mt-1 max-h-56 overflow-y-auto border-t border-line/70 pt-1">
                        <p className="px-3 pb-1 pt-2 text-[12px] font-semibold uppercase tracking-[0.08em] text-faint">
                          From your wardrobe
                        </p>
                        {wardrobeQuery.data
                          .filter((w) => w.image_url)
                          .map((w) => (
                            <button
                              key={w.id}
                              type="button"
                              onClick={() => {
                                setCustomItem(w);
                                setProduct(null);
                                setOutfit(null);
                                setLastStylistReply(null);
                                setAddMenuOpen(false);
                              }}
                              className="flex w-full items-center gap-3 rounded-[12px] px-3 py-2 text-left transition-colors hover:bg-paper-2"
                            >
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img
                                src={resolveMediaUrl(w.image_url)}
                                alt={w.name}
                                className="h-9 w-9 shrink-0 rounded-md object-cover object-top"
                              />
                              <span className="truncate text-[14px] text-ink">{w.name}</span>
                            </button>
                          ))}
                      </div>
                    )}
                  </div>
                </>
              )}

              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) uploadCustomItem.mutate(file);
                  e.target.value = "";
                }}
              />
            </div>

            <form
              className="flex flex-1 items-center gap-1.5"
              onSubmit={(e: FormEvent) => {
                e.preventDefault();
                if (!prompt.trim() || askStylist.isPending) return;
                askStylist.mutate(prompt);
              }}
            >
              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder={
                  baseLook
                    ? "What to add — e.g. gold necklace, gold ring, gold watch and pink khussa"
                    : "Type a look, e.g. pink bridal look"
                }
                className="h-11 flex-1 rounded-full bg-transparent px-2.5 text-[15px] text-ink outline-none placeholder:text-faint"
              />
              <VoiceInputButton
                onTranscript={(text) => setPrompt((p) => (p ? `${p} ${text}` : text))}
              />
              <button
                type="submit"
                disabled={!prompt.trim() || askStylist.isPending}
                aria-label="Ask stylist"
                className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-sage text-white transition-opacity disabled:opacity-40"
              >
                {askStylist.isPending ? (
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                ) : (
                  <span aria-hidden="true">↑</span>
                )}
              </button>
            </form>
          </div>

          {!lastStylistReply && (
            <div className="mt-3">
              <p className="text-[14px] text-muted">
                Tap a look, or type your own
              </p>
              <div className="tu-stagger mt-2 flex flex-wrap gap-2">
                {starterPrompts.map((text) => (
                  <button
                    key={text}
                    type="button"
                    disabled={askStylist.isPending}
                    onClick={() => {
                      setPrompt(text);
                      askStylist.mutate(text);
                    }}
                    className="tu-press min-h-[40px] rounded-full border border-line bg-surface px-4 py-1.5 text-left text-[15px] text-ink-soft transition-colors hover:border-sage hover:text-ink disabled:opacity-50"
                  >
                    {text}
                  </button>
                ))}
              </div>
            </div>
          )}

          {askStylist.isError && (
            <p className="mt-3 text-[14px] text-[#a4553f]" role="alert">
              {askStylist.error instanceof ApiError
                ? askStylist.error.detail
                : "Couldn't reach the stylist. Please try again."}
            </p>
          )}

          {uploadCustomItem.isPending && (
            <p className="mt-3 text-[14px] text-muted">Uploading your photo…</p>
          )}
          {uploadCustomItem.isError && (
            <p className="mt-3 text-[14px] text-[#a4553f]" role="alert">
              {uploadCustomItem.error instanceof ApiError
                ? uploadCustomItem.error.detail
                : "Couldn't upload that photo. Please try again."}
            </p>
          )}

          {customItem && (
            <div className="mt-4 flex animate-[tu-in-scale_0.35s_ease] items-center justify-between gap-3 rounded-[20px] border border-sage bg-sage-tint/30 p-4">
              <div className="flex min-w-0 items-center gap-3">
                {customItem.image_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={resolveMediaUrl(customItem.image_url)}
                    alt={customItem.name}
                    className="h-16 w-12 shrink-0 rounded-lg object-cover object-top"
                  />
                )}
                <div className="min-w-0">
                  <p className="text-[12px] font-semibold uppercase tracking-[0.1em] text-sage-deep">
                    Your own item
                  </p>
                  <p className="truncate text-[14px] font-semibold text-ink">{customItem.name}</p>
                  <p className="text-[12.5px] text-faint">Not shoppable — just your upload</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setCustomItem(null)}
                className="shrink-0 text-[13px] text-faint underline-offset-2 hover:text-ink hover:underline"
              >
                Clear
              </button>
            </div>
          )}

          {lastStylistReply && !outfit && !product && (
            <div className="mt-3 rounded-[18px] border border-dashed border-line p-4 text-[14px] text-muted">
              {lastStylistReply.summary || "No matching real products found for that — try a different prompt, or browse below."}
            </div>
          )}

          {(outfit || (product && lastStylistReply?.products.length === 1 && lastStylistReply.products[0].id === product.id)) && (
            <div ref={pickRef} className="scroll-mt-24">
              <StyledPicks
                items={
                  outfit
                    ? outfit.items.map((item) => ({
                        key: item.id,
                        product: item.product,
                        slot: item.slot,
                        rendered: outfit.rendered_item_ids.includes(item.id),
                        highlight: item.product.id === swappedInId,
                      }))
                    : [{ key: product!.id, product: product!, rendered: true, highlight: product!.id === swappedInId }]
                }
                alternatives={lastStylistReply?.alternatives ?? {}}
                summary={lastStylistReply?.summary}
                onUse={(alt, replaceId) => applyAlternative.mutate({ alt, replaceId })}
                onBuy={buyAlternative}
                busyId={
                  applyAlternative.isPending
                    ? applyAlternative.variables?.alt.retailer_product_id
                    : shopAlternative.isPending
                      ? shopAlternative.variables?.retailer_product_id
                      : undefined
                }
                onUndo={beforeSwap ? undoSwap : undefined}
                onClear={() => {
                  setOutfit(null);
                  setProduct(null);
                  setLastStylistReply(null);
                  setBeforeSwap(null);
                  setSwappedInId(null);
                }}
                defaultOpenKey={outfit ? null : product!.id}
              />
            </div>
          )}

          {(applyAlternative.isError || shopAlternative.isError) && (
            <p role="alert" className="mt-3 text-[14px] text-[#a4553f]">
              {(applyAlternative.error ?? shopAlternative.error) instanceof ApiError
                ? ((applyAlternative.error ?? shopAlternative.error) as ApiError).detail
                : "That option isn't available any more — try another one."}
            </p>
          )}

          <div className="mt-8 flex items-center gap-3 text-[13px] text-faint">
            <span className="h-px flex-1 bg-line" />
            or search for something specific
            <span className="h-px flex-1 bg-line" />
          </div>

          <div className="mt-4 flex gap-2">
            <input
              type="text"
              value={browseQuery}
              onChange={(e) => setBrowseQuery(e.target.value)}
              placeholder="e.g. blue denim jacket"
              className="h-11 min-w-0 flex-1 rounded-xl border border-line-strong bg-paper px-3.5 text-[15px] text-ink outline-none placeholder:text-faint focus:border-sage focus:ring-2 focus:ring-sage/25"
            />
            <Link
              href="/find-look"
              title="Upload a photo of an outfit and find its products"
              className="inline-flex h-11 shrink-0 items-center gap-2 rounded-xl border border-line-strong bg-surface px-3.5 text-[14.5px] font-semibold text-ink hover:border-sage"
            >
              <LensIcon size={18} />
              <span className="hidden sm:inline">Search by photo</span>
              <span className="sm:hidden">Photo</span>
            </Link>
          </div>
          <p className="mt-2 text-[12.5px] text-faint">
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
                <p className="text-[15px] text-muted">
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
              <div className="rounded-[20px] border border-line bg-surface p-8 text-center text-[15px] text-muted">
                {/[,]| and /i.test(browseQuery) ? (
                  <>
                    <p>This search looks for one product at a time. To find several at once, ask the stylist.</p>
                    <Button
                      size="sm"
                      className="mt-4"
                      disabled={askStylist.isPending}
                      onClick={() => {
                        const text = browseQuery;
                        setPrompt(text);
                        setBrowseQuery("");
                        askStylist.mutate(text);
                        window.scrollTo({ top: 0, behavior: "smooth" });
                      }}
                    >
                      Ask the stylist for these
                    </Button>
                  </>
                ) : (
                  "No real matches for that search — try different words."
                )}
              </div>
            )}

            {!liveSearchQuery.isFetching && liveSearchQuery.data && liveSearchQuery.data.length > 0 && (
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-5">
                {liveSearchQuery.data.map((item, i) => {
                  const selected =
                    product != null &&
                    !outfit &&
                    product.retailer.slug === item.retailer_slug &&
                    product.name === item.name;
                  const selecting =
                    selectLive.isPending &&
                    selectLive.variables?.retailer_product_id === item.retailer_product_id;
                  return (
                    <div
                      key={`${item.retailer_slug}:${item.retailer_product_id}`}
                      style={{ animationDelay: `${i * 50}ms` }}
                      className="animate-[tu-in-scale_0.4s_ease_both]"
                    >
                      <ProductCard
                        image={resolveMediaUrl(item.images[0])}
                        name={item.name}
                        priceCents={item.price_cents}
                        currency={item.currency}
                        shop={shopName(item.merchant_name, item.retailer_name)}
                        badge={selected ? "Selected" : item.featured ? FEATURED : fromTryOnUStore(item.retailer_slug) ? RECOMMENDED : null}
                        selected={selected}
                        busy={selecting}
                        primary={{
                          label: selected ? "Selected" : "Try this on",
                          onClick: () => selectLive.mutate(item),
                          disabled: selectLive.isPending || selected,
                        }}
                        secondary={{ label: "View in shop ↗", onClick: () => buyAlternative(item), disabled: shopAlternative.isPending }}
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {selectLive.isError && (
            <p className="mt-3 text-[14px] text-[#a4553f]" role="alert">
              {selectLive.error instanceof ApiError
                ? selectLive.error.detail
                : "Couldn't save that pick — it may no longer be available. Try again."}
            </p>
          )}

          {createJob.isError && (
            <p className="mt-4 text-[14px] text-[#a4553f]" role="alert">
              {createJob.error instanceof ApiError
                ? createJob.error.detail
                : "Couldn't start the try-on. Please try again."}
              {createJob.error instanceof ApiError && createJob.error.status === 402 && (
                <a href={buyHref} className="ml-2 font-semibold text-sage-deep underline underline-offset-2">
                  Buy credits
                </a>
              )}
            </p>
          )}

          {canMultiAngle && (product || outfit || customItem) && (
            <label className="mt-6 flex cursor-pointer items-start gap-3 rounded-[16px] border border-line bg-surface p-4 text-[14px]">
              <input
                type="checkbox"
                checked={multiAngle}
                onChange={(e) => setMultiAngle(e.target.checked)}
                className="mt-0.5 h-4 w-4 accent-sage"
              />
              <span>
                <span className="font-semibold text-ink">
                  Also render {PHOTO_KIND_LABEL[secondaryPhoto!.kind].toLowerCase()}
                </span>
                <span className="block text-[13px] text-muted">
                  Generates a second result from your {PHOTO_KIND_LABEL[secondaryPhoto!.kind].toLowerCase()} photo so
                  you can see both angles — uses a separate credit charge per angle.
                </span>
              </span>
            </label>
          )}

          {(product || outfit || customItem) && (
            <>
              {/* phones: the next step always in reach at the bottom of the screen */}
              <div className="h-24 md:hidden" aria-hidden="true" />
              <div className="fixed inset-x-0 bottom-[var(--tabbar-h)] z-40 border-t border-line bg-surface/95 px-4 py-3 shadow-[0_-6px_20px_rgba(20,20,16,0.08)] backdrop-blur md:hidden">
                <div className="mx-auto flex max-w-xl items-center gap-3">
                  <p className="min-w-0 flex-1 text-[14px] leading-snug text-ink-soft">
                    {sponsorName ? (
                      <>
                        <b className="text-ink">Free</b>
                        <br />
                        from {sponsorName}
                      </>
                    ) : tryOnCost !== null ? (
                      <>
                        Uses <b className="text-ink">{tryOnCost} credits</b>
                        <br />
                        You have {balance}
                      </>
                    ) : (
                      "Ready to try on"
                    )}
                  </p>
                  {sponsorName ? (
                    <Button size="md" disabled={createJob.isPending || selectLive.isPending} onClick={() => createJob.mutate(true)}>
                      {createJob.isPending ? "Starting…" : "Try on free"}
                    </Button>
                  ) : shortOfCredits ? (
                    <Button size="md" href={buyHref}>Buy credits</Button>
                  ) : (
                    <Button
                      size="md"
                      disabled={createJob.isPending || selectLive.isPending}
                      onClick={() => createJob.mutate(false)}
                    >
                      {createJob.isPending ? "Starting…" : outfit ? "Try on this look" : "Try it on"}
                    </Button>
                  )}
                </div>
              </div>
            </>
          )}

          {sponsorName && (
            <div className="mt-8 rounded-[20px] border border-sage/50 bg-sage-tint/30 p-5">
              <p className="font-display text-[22px] text-ink">Free try-on from {sponsorName}</p>
              <p className="mt-1 max-w-2xl text-[15.5px] leading-relaxed text-ink-soft">
                {sponsorName} pays for this try-on, so it costs you nothing. Your try-on picture will be shared with {sponsorName}{" "}
                so they can see their product on real people. Your name and email are never shared.
              </p>
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Button size="md" disabled={createJob.isPending || selectLive.isPending} onClick={() => createJob.mutate(true)}>
                  {createJob.isPending ? "Starting…" : `Try on free (share with ${sponsorName})`}
                </Button>
                {shortOfCredits ? (
                  <Button size="md" variant="outline" href={buyHref}>
                    Buy credits to keep it private
                  </Button>
                ) : (
                  <Button size="md" variant="outline" disabled={createJob.isPending || selectLive.isPending} onClick={() => createJob.mutate(false)}>
                    Use my {tryOnCost ?? ""} credits (keep it private)
                  </Button>
                )}
              </div>
            </div>
          )}

          <div className="mt-8 flex flex-wrap items-center gap-4">
            {sponsorName ? null : shortOfCredits && (product || outfit || customItem) ? (
              <Button size="md" href={buyHref}>
                Buy credits to try this on <span aria-hidden="true">→</span>
              </Button>
            ) : (
            <Button
              size="md"
              disabled={(!product && !outfit && !customItem) || createJob.isPending || selectLive.isPending}
              onClick={() => createJob.mutate(false)}
            >
              {createJob.isPending
                ? "Starting…"
                : multiAngle && canMultiAngle
                  ? "Generate both angles"
                  : "Generate try-on"}{" "}
              {!createJob.isPending && <span aria-hidden="true">→</span>}
            </Button>
            )}
            {tryOnCost !== null && !sponsorName && (product || outfit || customItem) && (
              <span className={`text-[13.5px] ${shortOfCredits ? "text-[#a4553f]" : "text-muted"}`}>
                Uses {tryOnCost} credits · you have {balance}
              </span>
            )}
            <button
              type="button"
              onClick={() => setStep(0)}
              className="font-display text-[15px] text-muted transition-colors hover:text-ink"
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
            {!allTerminal || anyCompleted ? (
              <div className="relative mx-auto grid h-24 w-24 place-items-center">
                <span className="absolute inset-0 rounded-full border-2 border-line" />
                <span className="absolute inset-0 animate-[tu-spin_0.9s_linear_infinite] rounded-full border-2 border-transparent border-t-sage" />
                <span className="absolute inset-2 animate-[tu-pulse-ring_1.8s_ease-out_infinite] rounded-full" />
                <span className="font-display text-[16px] text-ink">{clock(elapsedSec)}</span>
              </div>
            ) : (
              <div className="mx-auto grid h-24 w-24 place-items-center rounded-full border-2 border-[#c0503a]/40 text-[28px]">
                <XIcon size={16} />
              </div>
            )}

            <p className="mt-7 font-display text-[20px] text-ink">
              {jobsData.length === 0
                ? "Starting…"
                : jobIds.length > 1
                  ? jobsData.map((j) => `${PHOTO_KIND_LABEL[j.user_photo.kind]}: ${STAGE_LABEL[j.status]}`).join(" · ")
                  : // what the render is actually doing right now, when it
                    // says so — a minute of waiting should read as work
                    (jobsData[0].status === "processing" && jobsData[0].progress) ||
                    STAGE_LABEL[jobsData[0].status]}
            </p>
            <p className="mt-2 text-[14px] text-muted">
              {allTerminal && !anyCompleted
                ? jobsData.find((j) => j.status === "failed")?.error_message ||
                  "The AI provider couldn't complete this render. Your credits were refunded."
                : jobsData[0]?.status === "queued"
                  ? "Another render is using the worker — yours starts as soon as it finishes. This runs in the background, so you can leave and come back."
                  : `Rendering ${outfit ? `your ${outfit.items.length}-item outfit` : (product?.name ?? customItem?.name ?? "your look")}${jobIds.length > 1 ? ", both angles" : ""} — this runs as a background job, so you could leave and come back.`}
            </p>

            {(!allTerminal || anyCompleted) && (
              <div className="mx-auto mt-6 h-2 max-w-sm overflow-hidden rounded-full bg-paper-2">
                <div className="tu-flowline h-full w-full rounded-full opacity-70" />
              </div>
            )}

            <div className="mx-auto mt-5 flex max-w-sm flex-wrap items-center justify-center gap-2 text-[12px] text-faint">
              {jobIds.map((id) => (
                <span key={id} className="rounded-full border border-line px-2 py-1">
                  job #{id.slice(0, 8)}
                </span>
              ))}
              <span className="rounded-full border border-line px-2 py-1">
                {jobsData.length > 0 ? jobsData.reduce((sum, j) => sum + j.credit_cost, 0) : "—"} credit
                {jobsData.reduce((sum, j) => sum + j.credit_cost, 0) === 1 ? "" : "s"} reserved
              </span>
              <span className="rounded-full border border-line px-2 py-1">refund on failure</span>
            </div>

            {!allTerminal && elapsedSec > LONG_WAIT_SEC && (
              <div className="mx-auto mt-6 max-w-md rounded-2xl border border-[#c9a13b]/50 bg-[#c9a13b]/[0.08] p-4 text-left">
                <p className="text-[15.5px] font-semibold text-ink">This is taking longer than usual</p>
                <p className="mt-1 text-[14px] leading-snug text-muted">
                  You don&apos;t need to wait here. Open Try on again later to see your picture. If it can&apos;t be
                  finished, it stops by itself and you won&apos;t pay for a picture you didn&apos;t get.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setProduct(null);
                    setOutfit(null);
                    setCustomItem(null);
                    setJobIds([]);
                    setStep(1);
                  }}
                  className="tu-press mt-3 min-h-[44px] rounded-full border border-line-strong bg-surface px-4 text-[14.5px] font-semibold text-ink"
                >
                  Try something else meanwhile
                </button>
              </div>
            )}

            {allTerminal && !anyCompleted && (
              <div className="mt-6 flex justify-center gap-3">
                <Button
                  size="sm"
                  onClick={() => {
                    setProduct(null);
                    setOutfit(null);
                    setCustomItem(null);
                    setJobIds([]);
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
        completedJobs.length > 0 &&
        (completedJobs[0].outfit ? (
          <OutfitResultStep
            jobs={completedJobs}
            outfit={completedJobs[0].outfit}
            onAddMore={addMoreTo}
            onTryAnother={() => {
              setProduct(null);
              setOutfit(null);
              setCustomItem(null);
              setJobIds([]);
              setMultiAngle(false);
              setBaseLook(null);
              setStep(1);
            }}
            onStartOver={() => {
              setProduct(null);
              setOutfit(null);
              setCustomItem(null);
              setJobIds([]);
              setMultiAngle(false);
              setBaseLook(null);
              setStep(0);
            }}
          />
        ) : completedJobs[0].wardrobe_item || customItem ? (
          <WardrobeResultStep
            jobs={completedJobs}
            item={completedJobs[0].wardrobe_item || customItem!}
            onTryAnother={() => {
              setProduct(null);
              setOutfit(null);
              setCustomItem(null);
              setJobIds([]);
              setMultiAngle(false);
              setBaseLook(null);
              setStep(1);
            }}
            onStartOver={() => {
              setProduct(null);
              setOutfit(null);
              setCustomItem(null);
              setJobIds([]);
              setMultiAngle(false);
              setBaseLook(null);
              setStep(0);
            }}
          />
        ) : (
          (product || completedJobs[0].product) && (
            <ResultStep
              jobs={completedJobs}
              product={product || completedJobs[0].product!}
              onAddMore={addMoreTo}
              onTryAnother={() => {
                setProduct(null);
                setOutfit(null);
                setCustomItem(null);
                setJobIds([]);
                setMultiAngle(false);
                setBaseLook(null);
                setStep(1);
              }}
              onStartOver={() => {
                setProduct(null);
                setOutfit(null);
                setCustomItem(null);
                setJobIds([]);
                setMultiAngle(false);
                setBaseLook(null);
                setStep(0);
              }}
            />
          )
        ))}
    </section>
  );
}

function AngleGallery({
  jobs,
  activeIndex,
  onSelect,
}: {
  jobs: TryOnJob[];
  activeIndex: number;
  onSelect: (i: number) => void;
}) {
  if (jobs.length < 2) return null;
  return (
    <>
      {jobs.map((j, i) => (
        <button
          key={j.id}
          type="button"
          onClick={() => onSelect(i)}
          className={`rounded-full px-3 py-1.5 text-[12px] font-semibold shadow-sm transition-colors ${
            i === activeIndex ? "bg-sage text-white" : "bg-surface/90 text-ink hover:bg-surface"
          }`}
        >
          {PHOTO_KIND_LABEL[j.user_photo.kind]}
        </button>
      ))}
    </>
  );
}

function ResultStep({
  jobs,
  product,
  onAddMore,
  onTryAnother,
  onStartOver,
}: {
  jobs: TryOnJob[];
  product: Product;
  onAddMore: (job: TryOnJob) => void;
  onTryAnother: () => void;
  onStartOver: () => void;
}) {
  const [activeIndex, setActiveIndex] = useState(0);
  const job = jobs[activeIndex] ?? jobs[0];
  const totalCredits = jobs.reduce((sum, j) => sum + j.credit_cost, 0);

  return (
    <div key="s3" className="animate-[tu-in-scale_0.45s_cubic-bezier(0.22,1,0.36,1)]">
      <div className="flex flex-wrap items-center gap-2">
        <span className="grid h-6 w-6 place-items-center rounded-full bg-sage text-[13px] text-white"><CheckIcon size={14} /></span>
        <h1 className="font-display text-[clamp(24px,3.6vw,36px)] leading-tight text-ink">
          Here&rsquo;s <em>you</em>, in {product.name}
        </h1>
        <ShareLook jobId={job.id} />
      </div>

      <div className="mt-6 space-y-6">
        <div className="min-w-0">
          <LookBoard
            src={resolveMediaUrl(job.result!.image_url)}
            alt={`AI try-on result — ${product.name} — ${PHOTO_KIND_LABEL[job.user_photo.kind]}`}
            placements={job.result!.placements}
            caption={
              <p className="pointer-events-none absolute inset-x-0 bottom-0 z-10 bg-gradient-to-t from-black/55 to-transparent px-4 pb-3 pt-8 text-[12.5px] leading-snug text-white/90">
            AI-generated visualization — not a guarantee of exact fit, sizing, or color.
          </p>
            }
          >
            <div className="pointer-events-none absolute inset-x-3 top-3 z-10 flex flex-wrap items-start gap-2">
              <div className="pointer-events-auto flex flex-wrap items-start gap-2">
                <AngleGallery jobs={jobs} activeIndex={activeIndex} onSelect={setActiveIndex} />
              </div>
              <span className="ml-auto rounded-full bg-sage px-3 py-1.5 text-[12px] font-semibold text-white shadow-sm">
                AI try-on result{jobs.length > 1 ? ` · ${PHOTO_KIND_LABEL[job.user_photo.kind]}` : ""}
              </span>
            </div>
          </LookBoard>
        </div>
        <div className="flex flex-col rounded-[26px] border border-line bg-surface p-6">
          <p className="text-[12px] uppercase tracking-[0.14em] text-faint">
            {product.merchant_name ? `${product.retailer.name} · ${product.merchant_name}` : product.retailer.name}
          </p>
          <p className="mt-1 font-display text-[22px] text-ink">{product.name}</p>
          <p className="mt-1 text-[16px] text-muted">
            {(product.price_cents / 100).toFixed(2)} {product.currency.toUpperCase()}
          </p>
          <YourSize name={product.name} />

          <div className="mt-5 space-y-2 text-[14px] text-muted">
            <p className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-sage" /> {totalCredits} credit
              {totalCredits === 1 ? "" : "s"} used · {jobs.length > 1 ? `${jobs.length} angles` : "job"} completed
            </p>
            <p className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-sage" /> Rendered by {job.provider}
            </p>
          </div>

          <div className="mt-auto space-y-3 pt-6">
            <Button href={affiliateGoUrl(product.id, "tryon_result")} size="md" className="w-full">
              Shop now <span aria-hidden="true">→</span>
            </Button>
            <WhatsAppOrderButton productId={product.id} source="tryon_result" />
            <PriceAlertButton productId={product.id} />
            <SaveLookButton tryonResultId={job.result!.id} />
            <ShareLook jobId={job.id} variant="wide" />
            <PostToCommunity jobId={job.id} imageUrl={job.result?.image_url} />
            <AddMoreButton jobs={jobs} job={job} onAddMore={onAddMore} />
            <Button variant="outline" size="md" className="w-full" onClick={onTryAnother}>
              Try another product
            </Button>
            <button
              type="button"
              onClick={onStartOver}
              className="w-full text-center font-display text-[14px] text-muted transition-colors hover:text-ink"
            >
              Start over
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function OutfitItemThumb({
  item,
  rendered,
  number,
  highlight = false,
}: {
  item: OutfitItem;
  rendered: boolean;
  number?: number | null;
  highlight?: boolean;
}) {
  const thumb = resolveMediaUrl(item.product.images[0]?.url);
  return (
    <div
      className={`relative overflow-hidden rounded-[14px] border bg-surface ${
        highlight ? "tu-pop border-sage ring-2 ring-sage/40" : "border-line"
      }`}
    >
      {highlight && (
        <span className="absolute right-1 top-1 z-10 rounded-full bg-sage px-1.5 py-0.5 text-[10px] font-semibold text-white">
          Swapped in
        </span>
      )}
      <div className="relative aspect-square bg-paper-2">
        {thumb && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={thumb} alt={item.product.name} className="h-full w-full object-cover object-top" />
        )}
        <RetailerTag name={shopName(item.product.merchant_name, item.product.retailer?.name)} className="absolute left-1 top-1" />
        <span
          className={`absolute bottom-1 left-1 rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${
            rendered ? "bg-sage text-white" : "bg-surface/95 text-ink-soft"
          }`}
        >
          {number ? `${number} · on photo` : rendered ? "on photo" : "matched"}
        </span>
      </div>
      <p className="truncate px-1.5 py-1 text-[11.5px] text-ink-soft">{item.product.name}</p>
    </div>
  );
}

function OutfitResultStep({
  jobs,
  outfit,
  onAddMore,
  onTryAnother,
  onStartOver,
}: {
  jobs: TryOnJob[];
  outfit: Outfit;
  onAddMore: (job: TryOnJob) => void;
  onTryAnother: () => void;
  onStartOver: () => void;
}) {
  const renderedCount = outfit.rendered_item_ids.length;
  const [activeIndex, setActiveIndex] = useState(0);
  const job = jobs[activeIndex] ?? jobs[0];
  const totalCredits = jobs.reduce((sum, j) => sum + j.credit_cost, 0);

  return (
    <div key="s3-outfit" className="animate-[tu-in-scale_0.45s_cubic-bezier(0.22,1,0.36,1)]">
      <div className="flex flex-wrap items-center gap-2">
        <span className="grid h-6 w-6 place-items-center rounded-full bg-sage text-[13px] text-white"><CheckIcon size={14} /></span>
        <h1 className="font-display text-[clamp(24px,3.6vw,36px)] leading-tight text-ink">
          Here&rsquo;s <em>you</em>, styled
        </h1>
        <ShareLook jobId={job.id} />
      </div>

      <div className="mt-6 space-y-6">
        <div className="min-w-0">
          <LookBoard
            src={resolveMediaUrl(job.result!.image_url)}
            alt={`AI try-on result — styled outfit — ${PHOTO_KIND_LABEL[job.user_photo.kind]}`}
            placements={job.result!.placements}
            caption={
              <p className="pointer-events-none absolute inset-x-0 bottom-0 z-10 bg-gradient-to-t from-black/55 to-transparent px-4 pb-3 pt-8 text-[12.5px] leading-snug text-white/90">
            {job.look_round > 1
              ? lookCaption(job.result?.placements)
              : renderedCount === outfit.items.length
                ? "Every item in this outfit is on the photo."
                : `${renderedCount} of ${outfit.items.length} items drawn on the photo — the items marked “matched” are shown alongside with their own shop links.`}
          </p>
            }
          >
            <div className="pointer-events-none absolute inset-x-3 top-3 z-10 flex flex-wrap items-start gap-2">
              <div className="pointer-events-auto flex flex-wrap items-start gap-2">
                <AngleGallery jobs={jobs} activeIndex={activeIndex} onSelect={setActiveIndex} />
              </div>
              <span className="ml-auto rounded-full bg-sage px-3 py-1.5 text-[12px] font-semibold text-white shadow-sm">
                AI try-on result{jobs.length > 1 ? ` · ${PHOTO_KIND_LABEL[job.user_photo.kind]}` : ""}
              </span>
            </div>
          </LookBoard>
        </div>
        <div className="flex flex-col rounded-[26px] border border-line bg-surface p-6">
          <p className="text-[12px] uppercase tracking-[0.14em] text-faint">
            {outfit.items.length}-item outfit · {(outfit.total_price_cents / 100).toFixed(2)}{" "}
            {(outfit.items[0]?.product.currency ?? "usd").toUpperCase()}
          </p>

          <div className="mt-4 grid grid-cols-3 gap-2">
            {outfit.items.map((item) => (
              <OutfitItemThumb
                key={item.id}
                item={item}
                rendered={outfit.rendered_item_ids.includes(item.id)}
                number={markerNumber(job.result?.placements, item.product.id)}
              />
            ))}
          </div>

          <div className="mt-5 space-y-2 border-t border-line pt-4">
            {outfit.items.map((item) => (
              <div key={item.id} className="flex items-center justify-between gap-2 text-[13.5px]">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-ink-soft">{item.product.name}</span>
                  <span className="block text-[12px] text-faint">
                    {(item.product.price_cents / 100).toFixed(2)} {item.product.currency.toUpperCase()}
                    {shopName(item.product.merchant_name, item.product.retailer?.name) ? ` · ${shopName(item.product.merchant_name, item.product.retailer?.name)}` : ""}
                  </span>
                </span>
                <PriceAlertButton productId={item.product.id} size="small" />
                <Button
                  href={affiliateGoUrl(item.product.id, "tryon_result")}
                  size="sm"
                  variant="outline"
                  className="!h-7 shrink-0 !px-2.5 !text-[12px]"
                >
                  Shop now
                </Button>
              </div>
            ))}
          </div>

          <EarlierRounds job={job} outfit={outfit} />

          <div className="mt-5 space-y-2 text-[14px] text-muted">
            <p className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-sage" /> {totalCredits} credit
              {totalCredits === 1 ? "" : "s"} used · {jobs.length > 1 ? `${jobs.length} angles` : "job"} completed
            </p>
            <p className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-sage" /> Rendered by {job.provider}
            </p>
          </div>

          <div className="mt-auto space-y-3 pt-6">
            <SaveLookButton tryonResultId={job.result!.id} />
            <ShareLook jobId={job.id} variant="wide" />
            <PostToCommunity jobId={job.id} imageUrl={job.result?.image_url} />
            <AddMoreButton jobs={jobs} job={job} onAddMore={onAddMore} />
            <Button variant="outline" size="md" className="w-full" onClick={onTryAnother}>
              Try another look
            </Button>
            <button
              type="button"
              onClick={onStartOver}
              className="w-full text-center font-display text-[14px] text-muted transition-colors hover:text-ink"
            >
              Start over
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function WardrobeResultStep({
  jobs,
  item,
  onTryAnother,
  onStartOver,
}: {
  jobs: TryOnJob[];
  item: WardrobeItem;
  onTryAnother: () => void;
  onStartOver: () => void;
}) {
  const [activeIndex, setActiveIndex] = useState(0);
  const job = jobs[activeIndex] ?? jobs[0];
  const totalCredits = jobs.reduce((sum, j) => sum + j.credit_cost, 0);

  return (
    <div key="s3-wardrobe" className="animate-[tu-in-scale_0.45s_cubic-bezier(0.22,1,0.36,1)]">
      <div className="flex flex-wrap items-center gap-2">
        <span className="grid h-6 w-6 place-items-center rounded-full bg-sage text-[13px] text-white"><CheckIcon size={14} /></span>
        <h1 className="font-display text-[clamp(24px,3.6vw,36px)] leading-tight text-ink">
          Here&rsquo;s <em>you</em>, in {item.name}
        </h1>
        <ShareLook jobId={job.id} />
      </div>

      <div className="mt-6 space-y-6">
        <div className="min-w-0">
          <LookBoard
            src={resolveMediaUrl(job.result!.image_url)}
            alt={`AI try-on result — ${item.name} — ${PHOTO_KIND_LABEL[job.user_photo.kind]}`}
            placements={job.result!.placements}
            caption={
              <p className="pointer-events-none absolute inset-x-0 bottom-0 z-10 bg-gradient-to-t from-black/55 to-transparent px-4 pb-3 pt-8 text-[12.5px] leading-snug text-white/90">
            AI-generated visualization — not a guarantee of exact fit, sizing, or color.
          </p>
            }
          >
            <div className="pointer-events-none absolute inset-x-3 top-3 z-10 flex flex-wrap items-start gap-2">
              <div className="pointer-events-auto flex flex-wrap items-start gap-2">
                <AngleGallery jobs={jobs} activeIndex={activeIndex} onSelect={setActiveIndex} />
              </div>
              <span className="ml-auto rounded-full bg-sage px-3 py-1.5 text-[12px] font-semibold text-white shadow-sm">
                AI try-on result{jobs.length > 1 ? ` · ${PHOTO_KIND_LABEL[job.user_photo.kind]}` : ""}
              </span>
            </div>
          </LookBoard>
        </div>
        <div className="flex flex-col rounded-[26px] border border-line bg-surface p-6">
          <p className="text-[12px] uppercase tracking-[0.14em] text-faint">Your own item</p>
          <p className="mt-1 font-display text-[22px] text-ink">{item.name}</p>
          <p className="mt-1 text-[14px] text-muted">
            Not shoppable — this is your own upload, not a catalog product.
          </p>

          <div className="mt-5 space-y-2 text-[14px] text-muted">
            <p className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-sage" /> {totalCredits} credit
              {totalCredits === 1 ? "" : "s"} used · {jobs.length > 1 ? `${jobs.length} angles` : "job"} completed
            </p>
            <p className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-sage" /> Rendered by {job.provider}
            </p>
          </div>

          <div className="mt-auto space-y-3 pt-6">
            <SaveLookButton tryonResultId={job.result!.id} />
            <ShareLook jobId={job.id} variant="wide" />
            <PostToCommunity jobId={job.id} imageUrl={job.result?.image_url} />
            <Button variant="outline" size="md" className="w-full" onClick={onTryAnother}>
              Try another item
            </Button>
            <button
              type="button"
              onClick={onStartOver}
              className="w-full text-center font-display text-[14px] text-muted transition-colors hover:text-ink"
            >
              Start over
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function lookCaption(placements: ResultPlacement[] | null | undefined): string {
  const all = placements ?? [];
  const drawn = all.filter((p) => p.drawn).length;
  return drawn === all.length
    ? "Every item in this look is on the photo."
    : `${drawn} of ${all.length} items in this look are on the photo — the items marked “matched” are shown with their own shop links.`;
}

/** "Add more to this look": a further round, drawn onto this finished image.
 *  Only for a single-angle look that still has rounds left. */
function AddMoreButton({
  jobs,
  job,
  onAddMore,
}: {
  jobs: TryOnJob[];
  job: TryOnJob;
  onAddMore: (job: TryOnJob) => void;
}) {
  if (jobs.length !== 1 || !job.result) return null;
  if (job.look_round >= job.max_look_rounds) {
    return (
      <p className="text-center text-[13px] text-faint">
        This look has its {job.max_look_rounds} rounds. Start a new look to add more.
      </p>
    );
  }
  return (
    <Button size="md" className="w-full" onClick={() => onAddMore(job)}>
      Add more to this look · round {job.look_round + 1} of {job.max_look_rounds}
    </Button>
  );
}




/** Products from earlier rounds that are still in this look. */
function EarlierRounds({ job, outfit }: { job: TryOnJob; outfit: Outfit }) {
  if (job.look_round <= 1) return null;
  const thisRound = new Set(outfit.items.map((i) => i.product.id));
  const earlier = (job.result?.placements ?? []).filter((p) => !p.product_id || !thisRound.has(p.product_id));
  if (earlier.length === 0) return null;
  return (
    <div className="mt-5 border-t border-line pt-4">
      <p className="text-[12px] uppercase tracking-[0.14em] text-faint">From earlier rounds</p>
      <div className="mt-2 space-y-2">
        {earlier.map((p, i) => (
          <div key={`${p.product_id ?? p.name}-${i}`} className="flex items-center justify-between gap-2 text-[13.5px]">
            <span className="min-w-0 flex-1">
              <span className="block truncate text-ink-soft">{p.name}</span>
              <span className="block text-[12px] text-faint">
                {p.drawn ? "on photo" : "matched"}
                {retailerFromImage(p.image_url) ? ` · ${retailerFromImage(p.image_url)}` : ""}
              </span>
            </span>
            {p.product_id && (
              <Button
                href={affiliateGoUrl(p.product_id, "tryon_result")}
                size="sm"
                variant="outline"
                className="!h-7 shrink-0 !px-2.5 !text-[12px]"
              >
                Shop now
              </Button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function SaveLookButton({ tryonResultId }: { tryonResultId: string }) {
  const save = useMutation({ mutationFn: () => savedLooksApi.save(tryonResultId) });

  if (save.isSuccess) {
    return (
      <Button variant="outline" size="md" className="w-full" disabled>
        Saved to your lookbook
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
