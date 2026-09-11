"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/lib/api/client";
import { auth } from "@/lib/api/endpoints";
import type { User } from "@/lib/api/types";

export const SESSION_QUERY_KEY = ["session", "me"] as const;

/** Current user, or `null` when signed out — never throws for the
 * expected-401 case so callers can render a clean "signed out" state. */
export function useSession() {
  const query = useQuery<User | null>({
    queryKey: SESSION_QUERY_KEY,
    queryFn: async () => {
      try {
        return await auth.me();
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return null;
        throw err;
      }
    },
    staleTime: 60_000,
    retry: false,
  });

  return {
    user: query.data ?? null,
    isLoading: query.isLoading,
    isError: query.isError,
    refetch: query.refetch,
  };
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: auth.login,
    onSuccess: (data) => qc.setQueryData(SESSION_QUERY_KEY, data.user),
  });
}

export function useRegister() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: auth.register,
    onSuccess: (data) => qc.setQueryData(SESSION_QUERY_KEY, data.user),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: auth.logout,
    onSuccess: () => qc.setQueryData(SESSION_QUERY_KEY, null),
  });
}
