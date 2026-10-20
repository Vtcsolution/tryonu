"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AccountSettings } from "@/components/account/AccountSettings";
import { useSession } from "@/lib/auth/useSession";

export function AccountPage() {
  const router = useRouter();
  const { user, isLoading } = useSession();

  useEffect(() => {
    if (!isLoading && !user) router.replace("/sign-in?next=/account");
  }, [isLoading, user, router]);

  if (!user) {
    return <div className="mx-auto my-24 h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />;
  }

  return (
    <section className="mx-auto w-[min(1000px,calc(100%-32px))] pb-10 pt-4 lg:py-16">
      <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep max-lg:hidden">My account</p>
      <h1 className="mt-1 font-display text-[clamp(28px,4vw,40px)] leading-tight text-ink max-lg:hidden">Profile & password</h1>
      <div className="lg:mt-8">
        <AccountSettings user={user} />
      </div>
    </section>
  );
}
