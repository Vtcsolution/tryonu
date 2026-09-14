"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { AuthCard } from "@/components/auth/AuthCard";
import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api/client";
import { auth } from "@/lib/api/endpoints";
import { SESSION_QUERY_KEY } from "@/lib/auth/useSession";

export function VerifyEmailPanel() {
  const params = useSearchParams();
  const token = params.get("token");
  const qc = useQueryClient();
  const attempted = useRef(false);

  const verify = useMutation({
    mutationFn: auth.verifyEmail,
    onSuccess: () => qc.invalidateQueries({ queryKey: SESSION_QUERY_KEY }),
  });

  useEffect(() => {
    if (token && !attempted.current) {
      attempted.current = true;
      verify.mutate({ token });
    }
  }, [token, verify]);

  if (!token) {
    return (
      <AuthCard kicker="Account setup" title={<>Link is invalid</>}>
        <p className="text-[14px] leading-relaxed text-ink-soft">
          This verification link is missing or malformed. Sign in and use “Resend verification
          email” from your account menu to get a new one.
        </p>
      </AuthCard>
    );
  }

  if (verify.isSuccess) {
    return (
      <AuthCard
        kicker="Account setup"
        title={
          <>
            Email <em>verified</em>
          </>
        }
        subtitle="Your account is fully set up."
      >
        <Button href="/preferences?next=%2Ftry" size="md" className="w-full">
          Start your first try-on <span aria-hidden="true">→</span>
        </Button>
      </AuthCard>
    );
  }

  if (verify.isError) {
    return (
      <AuthCard kicker="Account setup" title={<>Verification failed</>}>
        <p className="text-[14px] leading-relaxed text-ink-soft">
          {verify.error instanceof ApiError
            ? verify.error.detail
            : "This link is invalid or has expired."}{" "}
          Sign in and use “Resend verification email” from your account menu to get a new one.
        </p>
        <Link
          href="/sign-in"
          className="mt-5 inline-block font-semibold text-sage hover:text-sage-deep"
        >
          Back to sign in
        </Link>
      </AuthCard>
    );
  }

  return (
    <AuthCard kicker="Account setup" title={<>Verifying your email…</>}>
      <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
    </AuthCard>
  );
}
