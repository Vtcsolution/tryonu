"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api/client";
import { shared as sharedApi } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";
import { clearReturnTo, rememberReturnTo } from "@/lib/returnTo";

/** Signed in: copy the shared look's products into the visitor's own outfit and
 * open the try-on page with it (their photo comes first if they have none yet). */
export function TrySharedLook({ token }: { token: string }) {
  const router = useRouter();
  const { user, isLoading } = useSession();
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (isLoading || started.current) return;
    started.current = true;
    if (!user) {
      rememberReturnTo(`/look/${token}/try`);
      router.replace(`/sign-up?next=${encodeURIComponent(`/look/${token}/try`)}`);
      return;
    }
    sharedApi
      .tryThis(token)
      .then((res) => {
        clearReturnTo(`/look/${token}/try`);
        router.replace(res.outfit_id ? `/try?outfit=${res.outfit_id}` : `/try?product=${res.product_id}`);
      })
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Couldn't open this look. Please try again."));
  }, [isLoading, user, token, router]);

  return (
    <section className="mx-auto grid min-h-[50vh] w-[min(640px,calc(100%-32px))] place-items-center py-16 text-center">
      {error ? (
        <div>
          <p className="font-display text-[26px] text-ink">This look can&apos;t be opened</p>
          <p className="mt-2 text-[16px] text-ink-soft">{error}</p>
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            <Button href={`/look/${token}`} size="md" variant="outline">Back to the look</Button>
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
