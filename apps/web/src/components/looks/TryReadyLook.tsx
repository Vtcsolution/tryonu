"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api/client";
import { readyLooks } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";
import { clearReturnTo, rememberReturnTo } from "@/lib/returnTo";

/** Signed in: the Ready look's products become the shopper's own outfit, and
 * the try-on page opens with it (their photo first if they have none; the $1
 * first outfit there if they have no credits, coming back to this look).
 * Not signed in: create an account first, remembering this look. */
export function TryReadyLook({ lookId }: { lookId: string }) {
  const router = useRouter();
  const { user, isLoading } = useSession();
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);
  const here = `/looks/${lookId}/try`;

  useEffect(() => {
    if (isLoading || started.current) return;
    started.current = true;
    if (!user) {
      rememberReturnTo(here);
      router.replace(`/sign-up?next=${encodeURIComponent(here)}`);
      return;
    }
    readyLooks
      .tryIt(lookId)
      .then((res) => {
        clearReturnTo(here);
        router.replace(res.outfit_id ? `/try?outfit=${res.outfit_id}` : `/try?product=${res.product_id}`);
      })
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Couldn't open this look. Please try again."));
  }, [isLoading, user, lookId, here, router]);

  return (
    <section className="mx-auto grid min-h-[50vh] w-[min(640px,calc(100%-32px))] place-items-center py-16 text-center">
      {error ? (
        <div>
          <p className="font-display text-[26px] text-ink">This look can&apos;t be opened</p>
          <p className="mt-2 text-[16px] text-ink-soft">{error}</p>
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            <Button href="/looks" size="md" variant="outline">See all ready looks</Button>
            <Button href="/try" size="md">Try on something else</Button>
          </div>
        </div>
      ) : (
        <div>
          <div className="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-line border-t-sage" aria-hidden="true" />
          <p className="mt-4 font-display text-[24px] text-ink">Getting this look ready for you…</p>
        </div>
      )}
    </section>
  );
}
