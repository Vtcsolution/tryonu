"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api/client";
import { tryon as tryonApi, type TryOnReportReason } from "@/lib/api/endpoints";
import type { TryOnJob } from "@/lib/api/types";

/** "Try another look": a new picture of exactly the same products on the same
 *  photo. To wear something else, the shopper changes the products first. */
export function TryAnotherLook({ job, onStarted }: { job: TryOnJob; onStarted: (jobs: TryOnJob[]) => void }) {
  const qc = useQueryClient();
  const again = useMutation({
    mutationFn: () =>
      tryonApi.create({
        user_photo_id: job.user_photo.id,
        ...(job.outfit ? { outfit_id: job.outfit.id } : {}),
        ...(job.product ? { product_id: job.product.id } : {}),
        ...(job.wardrobe_item ? { wardrobe_item_id: job.wardrobe_item.id } : {}),
        ...(job.base_job_id ? { base_job_id: job.base_job_id } : {}),
      }),
    onSuccess: (next) => {
      qc.invalidateQueries({ queryKey: ["session", "me"] }); // credits just changed
      onStarted([next]);
    },
  });
  return (
    <div>
      <Button size="md" variant="outline" className="w-full" disabled={again.isPending} onClick={() => again.mutate()}>
        {again.isPending ? "Starting…" : `Try another look · ${job.credit_cost} credits`}
      </Button>
      <p className="mt-1 text-center text-[13px] text-muted">A new picture with the same products.</p>
      {again.isError && (
        <p role="alert" className="mt-1 text-center text-[14px] text-[#a4553f]">
          {again.error instanceof ApiError ? again.error.detail : "Couldn't start it. Please try again."}
        </p>
      )}
    </div>
  );
}

const REASONS: [TryOnReportReason, string][] = [
  ["wrong_product", "A product doesn't look like the real one"],
  ["merged", "Two products were merged into one"],
  ["extra_item", "Something was added that I didn't choose"],
  ["not_me", "It doesn't look like me"],
  ["bad_quality", "The picture looks wrong or unrealistic"],
  ["other", "Something else"],
];

/** "Report incorrect result": goes to the team, who check the picture and give the credits back when it's wrong. */
export function ReportResult({ jobId }: { jobId: string }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<TryOnReportReason>("wrong_product");
  const [note, setNote] = useState("");
  const report = useMutation({ mutationFn: () => tryonApi.report(jobId, { reason, note: note.trim() || undefined }) });
  const already = report.error instanceof ApiError && report.error.status === 409;

  if (report.isSuccess || already) {
    return (
      <p className="rounded-[14px] bg-sage-tint/60 px-3 py-2.5 text-center text-[14px] text-ink">
        Thank you. We&apos;ll check this picture, and if it came out wrong your credits come back and we&apos;ll email you.
      </p>
    );
  }
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="w-full text-center text-[14px] text-muted underline-offset-2 hover:text-ink hover:underline">
        Report incorrect result
      </button>
    );
  }
  return (
    <div className="rounded-[14px] border border-line p-3">
      <label className="block text-[14px] font-semibold text-ink">
        What went wrong?
        <select
          value={reason}
          onChange={(e) => setReason(e.target.value as TryOnReportReason)}
          className="mt-1.5 h-11 w-full rounded-xl border border-line-strong bg-paper px-3 text-[15px] font-normal text-ink"
        >
          {REASONS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        maxLength={1000}
        rows={2}
        placeholder="Anything else we should know? (optional)"
        aria-label="More details"
        className="mt-2 w-full rounded-xl border border-line-strong bg-paper p-2.5 text-[15px] text-ink"
      />
      {report.isError && !already && <p role="alert" className="mt-1 text-[14px] text-[#a4553f]">Couldn&apos;t send it. Please try again.</p>}
      <div className="mt-2 flex gap-2">
        <Button size="sm" disabled={report.isPending} onClick={() => report.mutate()}>
          {report.isPending ? "Sending…" : "Send report"}
        </Button>
        <Button size="sm" variant="outline" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
