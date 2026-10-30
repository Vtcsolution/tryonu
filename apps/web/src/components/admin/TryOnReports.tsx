"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { mediaThumb } from "@/lib/api/client";
import { adminTryonReports } from "@/lib/api/endpoints";
import { ErrorNote, SmallButton, errorText, when } from "./ui";

const REASON: Record<string, string> = {
  wrong_product: "A product doesn't look like the real one",
  merged: "Two products merged into one",
  extra_item: "Something added they didn't choose",
  not_me: "Doesn't look like them",
  bad_quality: "Looks wrong or unrealistic",
  other: "Something else",
};
const KEY = ["admin", "tryon-reports"];

/** Try-ons shoppers reported: look at the picture, then refund or dismiss. Shown only when there are some. */
export function TryOnReports() {
  const qc = useQueryClient();
  const reports = useQuery({ queryKey: KEY, queryFn: () => adminTryonReports.list() });
  const answer = useMutation({
    mutationFn: ({ id, refund }: { id: string; refund: boolean }) => (refund ? adminTryonReports.refund(id) : adminTryonReports.dismiss(id)),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
  if (!reports.data?.length && !reports.isError) return null;
  return (
    <div className="mb-6 rounded-[18px] border border-[#c9a13b]/50 bg-[#c9a13b]/[0.06] p-4">
      <p className="text-[16px] font-semibold text-ink">Reported by shoppers ({reports.data?.length ?? 0})</p>
      {reports.isError && <ErrorNote>{errorText(reports.error)}</ErrorNote>}
      {answer.isError && <ErrorNote>{errorText(answer.error)}</ErrorNote>}
      <div className="mt-3 space-y-3">
        {reports.data?.map((r) => (
          <div key={r.id} className="flex flex-wrap gap-3 rounded-[14px] border border-line bg-surface p-3">
            {r.image_url && (
              <a href={r.image_url} target="_blank" rel="noopener noreferrer">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={mediaThumb(r.image_url, 240)} alt="The reported try-on" className="h-28 w-20 rounded-lg bg-paper-2 object-contain" />
              </a>
            )}
            <div className="min-w-0 flex-1">
              <p className="text-[15px] font-semibold text-ink">{REASON[r.reason] ?? r.reason}</p>
              {r.note && <p className="mt-0.5 text-[14px] text-ink-soft">{r.note}</p>}
              <p className="mt-1 text-[13px] text-muted">
                {r.user_email ?? "—"} · {r.what} · {when(r.created_at)}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <SmallButton tone="primary" disabled={answer.isPending} onClick={() => answer.mutate({ id: r.id, refund: true })}>
                  Refund {r.credit_cost} credits
                </SmallButton>
                <SmallButton disabled={answer.isPending} onClick={() => answer.mutate({ id: r.id, refund: false })}>
                  Dismiss
                </SmallButton>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
