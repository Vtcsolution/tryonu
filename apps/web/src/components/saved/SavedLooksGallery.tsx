"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { EarnRules, earnRuleLines } from "@/components/referrals/EarnRules";
import { LookThumb, lookPrice, lookTitle } from "@/components/saved/SavedLookDetail";
import { ShareLook } from "@/components/try/ShareLook";
import { Button } from "@/components/ui/Button";
import { resolveMediaUrl } from "@/lib/api/client";
import { referrals as referralsApi, savedLooks as savedLooksApi } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";
import type { SavedLook } from "@/lib/api/types";

/** The shopper's own lookbook: every saved look, with its products, View look and Share. */
export function SavedLooksGallery() {
  const router = useRouter();
  const { user, isLoading: sessionLoading } = useSession();

  useEffect(() => {
    if (!sessionLoading && !user) router.replace("/sign-in?next=/saved");
  }, [sessionLoading, user, router]);

  const looksQuery = useQuery({
    queryKey: ["saved-looks"],
    queryFn: savedLooksApi.list,
    enabled: !!user,
  });

  if (sessionLoading || !user) {
    return (
      <section className="tu-container py-24 text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
      </section>
    );
  }

  return (
    <section className="tu-container flex flex-col pb-10 pt-4 lg:py-16">
      <h1 className="font-display text-[clamp(28px,4vw,42px)] leading-tight text-ink max-lg:hidden">
        Your <em>saved looks</em>
      </h1>
      <p className="mt-2 max-w-2xl text-[16.5px] leading-relaxed text-ink-soft max-lg:hidden">
        Your saved looks. Open one to see its products, or share it with friends.
      </p>

      {/* phones: the looks first, inviting friends after them */}
      <div className="max-lg:order-2">
        <ShareAndEarn />
      </div>

      <div className="lg:mt-8">
        {looksQuery.isLoading && (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="aspect-[3/4] animate-pulse rounded-[22px] bg-paper-2" />
            ))}
          </div>
        )}

        {looksQuery.data && looksQuery.data.length === 0 && (
          <div className="rounded-[22px] border border-dashed border-line p-10 text-center">
            <p className="text-[16px] text-muted">
              No saved looks yet. Try something on and press <b>Save this look</b> on the result.
            </p>
            <Button href="/try" size="md" className="mt-5">
              Start a try-on <span aria-hidden="true">→</span>
            </Button>
          </div>
        )}

        {looksQuery.data && looksQuery.data.length > 0 && (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
            {looksQuery.data.map((look) => (
              <SavedLookCard key={look.id} look={look} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

/** Share and earn: the shopper's invite link, and what it has earned so far. */
function ShareAndEarn() {
  const me = useQuery({ queryKey: ["referrals", "me"], queryFn: referralsApi.me, staleTime: 5 * 60_000 });
  const [highlight, setHighlight] = useState(false);
  useEffect(() => {
    if (window.location.hash === "#earn") {
      setHighlight(true);
      document.getElementById("earn")?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, []);
  if (!me.data || earnRuleLines(me.data).length === 0) return null;
  const d = me.data;
  return (
    <div
      id="earn"
      className={`mt-6 flex flex-wrap items-center gap-5 rounded-[24px] border p-5 md:p-6 ${
        highlight ? "border-sage bg-sage-tint/50 ring-2 ring-sage/40" : "border-sage/40 bg-sage-tint/25"
      }`}
    >
      <div className="min-w-0 flex-1 basis-[320px]">
        <p className="font-display text-[24px] text-ink">Invite friends &amp; earn credits</p>
        <div className="mt-2">
          <EarnRules summary={d} compact />
        </div>
        <p className="mt-3 text-[14px] text-muted">
          Friends joined: <b className="text-ink">{d.friends_joined}</b> · tried on: <b className="text-ink">{d.friends_tried}</b> · shops:{" "}
          <b className="text-ink">{d.stores_bought}</b> · you earned: <b className="text-ink">{d.credits_earned} credits</b> ·{" "}
          <a href="/earn" className="font-semibold text-sage-deep hover:underline">How it works</a>
        </p>
      </div>
      <div className="w-full sm:w-auto sm:min-w-[300px]">
        <ShareLook
          url={d.link}
          variant="wide"
          label="Share my invite link"
          title="Invite friends to TryOnU"
          message="See yourself in any outfit before you buy it. Join me on TryOnU:"
          earns
        />
      </div>
    </div>
  );
}

function SavedLookCard({ look }: { look: SavedLook }) {
  const qc = useQueryClient();
  const [confirmRemove, setConfirmRemove] = useState(false);
  const remove = useMutation({
    mutationFn: () => savedLooksApi.remove(look.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["saved-looks"] }),
  });
  const image = resolveMediaUrl(look.image_url);
  const items = look.items ?? [];
  const price = lookPrice(look);
  const href = `/saved/${look.id}`;

  return (
    <article className="flex flex-col overflow-hidden rounded-[22px] border border-line bg-surface">
      {/* the whole picture, never cropped */}
      <Link href={href} className="group relative block aspect-[3/4] bg-paper-2" aria-label={`View ${lookTitle(look)}`}>
        {image && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={image} alt={lookTitle(look)} loading="lazy" className="h-full w-full object-contain" />
        )}
      </Link>

      <div className="flex flex-1 flex-col p-4">
        <p className="truncate text-[16.5px] font-semibold text-ink">{lookTitle(look)}</p>
        <p className="mt-0.5 text-[14px] text-muted">
          {items.length > 0 ? `${items.length} ${items.length === 1 ? "product" : "products"}` : "Your own item"}
          {price ? ` · ${price}` : ""} · {new Date(look.created_at).toLocaleDateString()}
        </p>

        {items.length > 0 && (
          <div className="mt-3 flex gap-1.5">
            {items.slice(0, 5).map((item) => (
              <LookThumb key={item.id} item={item} className="h-12 w-12 rounded-[10px]" />
            ))}
            {items.length > 5 && (
              <span className="grid h-12 w-12 place-items-center rounded-[10px] bg-paper-2 text-[13px] font-semibold text-ink-soft">
                +{items.length - 5}
              </span>
            )}
          </div>
        )}

        <div className="mt-auto space-y-2 pt-4">
          <Link
            href={href}
            className="tu-press flex min-h-[48px] w-full items-center justify-center rounded-full bg-sage text-[16px] font-semibold text-white hover:bg-sage-deep"
          >
            View look &amp; products →
          </Link>
          {look.tryon_job_id && <ShareLook jobId={look.tryon_job_id} variant="wide" />}
          <div className="pt-1 text-center text-[13.5px]">
            {confirmRemove ? (
              <span className="inline-flex flex-wrap items-center justify-center gap-3 text-ink-soft">
                Remove from saved looks?
                <button
                  type="button"
                  disabled={remove.isPending}
                  onClick={() => remove.mutate()}
                  className="font-semibold text-[#a4553f] hover:underline"
                >
                  Yes, remove
                </button>
                <button type="button" onClick={() => setConfirmRemove(false)} className="text-muted hover:text-ink">
                  Cancel
                </button>
              </span>
            ) : (
              <button type="button" onClick={() => setConfirmRemove(true)} className="text-muted hover:text-[#a4553f]">
                Remove
              </button>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}
