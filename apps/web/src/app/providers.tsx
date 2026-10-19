"use client";

import { useState } from "react";
import {
  QueryClient,
  QueryClientProvider,
  isServer,
} from "@tanstack/react-query";
import { AnalyticsTracker } from "@/components/analytics/AnalyticsTracker";
import { CountryGate } from "@/components/auth/CountryGate";
import { PwaSetup } from "@/components/pwa/InstallApp";
import { ReferralCapture } from "@/components/referrals/ReferralCapture";

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000,
        refetchOnWindowFocus: false,
        retry: 1,
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined;

function getQueryClient() {
  if (isServer) return makeQueryClient();
  if (!browserQueryClient) browserQueryClient = makeQueryClient();
  return browserQueryClient;
}

/**
 * App-wide client providers. TanStack Query is wired up now so that
 * try-on job polling / catalog queries drop in without re-plumbing.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(getQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      <AnalyticsTracker />
      <CountryGate />
      <ReferralCapture />
      <PwaSetup />
      {children}
    </QueryClientProvider>
  );
}
