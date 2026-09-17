"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { resolveMediaUrl } from "@/lib/api/client";
import { admin as adminApi } from "@/lib/api/endpoints";
import type { AdminTryOnJob, JobStatus } from "@/lib/api/types";
import { Badge, ErrorNote, PAGE_SIZE, Pager, SectionHeader, SmallButton, Table, TableSkeleton, errorText, when } from "./ui";

const STATUSES: (JobStatus | "")[] = ["", "queued", "processing", "completed", "failed", "cancelled"];

const STATUS_TONE: Record<JobStatus, "good" | "bad" | "warn" | "neutral"> = {
  completed: "good",
  failed: "bad",
  cancelled: "neutral",
  queued: "warn",
  processing: "warn",
};

function targetLabel(job: AdminTryOnJob): string {
  if (job.outfit) return `Outfit · ${job.outfit.items.length} items`;
  if (job.wardrobe_item) return `Own item · ${job.wardrobe_item.name}`;
  return job.product?.name ?? "—";
}

export function TryOnsTab() {
  const qc = useQueryClient();
  const [status, setStatus] = useState<JobStatus | "">("");
  const [offset, setOffset] = useState(0);

  const query = useQuery({
    queryKey: ["admin", "tryons", status, offset],
    queryFn: () => adminApi.tryonJobs({ status_filter: status || undefined, limit: PAGE_SIZE, offset }),
    refetchInterval: 10_000,
  });

  const cancel = useMutation({
    mutationFn: (jobId: string) => adminApi.cancelTryonJob(jobId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "tryons"] });
      qc.invalidateQueries({ queryKey: ["admin", "audit"] });
    },
  });

  return (
    <div>
      <SectionHeader title="Try-on jobs" hint="Every render across all users. Stuck jobs can be cancelled with a refund.">
        <div className="flex flex-wrap gap-1.5">
          {STATUSES.map((s) => (
            <button
              key={s || "all"}
              type="button"
              onClick={() => {
                setStatus(s);
                setOffset(0);
              }}
              className={`rounded-full px-3 py-1 text-[12px] ${
                status === s ? "bg-ink text-paper" : "border border-line text-ink-soft hover:border-line-strong"
              }`}
            >
              {s || "All"}
            </button>
          ))}
        </div>
      </SectionHeader>

      {cancel.isError && <div className="mb-3"><ErrorNote>{errorText(cancel.error)}</ErrorNote></div>}

      {query.isLoading ? (
        <TableSkeleton />
      ) : query.isError || !query.data ? (
        <ErrorNote>{errorText(query.error, "Couldn't load try-on jobs.")}</ErrorNote>
      ) : (
        <>
          <Table
            columns={["Result", "User", "Target", "Status", "Credits", "Created", ""]}
            rows={query.data.items.map((job) => [
              job.result ? (
                <a key="r" href={resolveMediaUrl(job.result.image_url)} target="_blank" rel="noopener noreferrer">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={resolveMediaUrl(job.result.image_url)}
                    alt="Try-on result"
                    className="h-14 w-11 rounded-md bg-paper-2 object-contain"
                  />
                </a>
              ) : (
                <span key="r" className="text-faint">—</span>
              ),
              job.user_email ?? "—",
              <span key="t" className="line-clamp-2 max-w-[240px]">{targetLabel(job)}</span>,
              <div key="s" className="space-y-1">
                <Badge tone={STATUS_TONE[job.status]}>{job.status}</Badge>
                {job.error_message && (
                  <p className="line-clamp-2 max-w-[220px] text-[11px] text-muted" title={job.error_message}>
                    {job.error_message}
                  </p>
                )}
              </div>,
              job.credit_cost,
              when(job.created_at),
              job.status === "queued" || job.status === "processing" ? (
                <SmallButton
                  key="c"
                  tone="danger"
                  disabled={cancel.isPending}
                  onClick={() => {
                    if (window.confirm(`Cancel this job and refund ${job.credit_cost} credits to ${job.user_email}?`)) {
                      cancel.mutate(job.id);
                    }
                  }}
                >
                  Cancel + refund
                </SmallButton>
              ) : (
                ""
              ),
            ])}
            empty="No try-on jobs match this filter."
          />
          <Pager offset={offset} total={query.data.total} onChange={setOffset} />
        </>
      )}
    </div>
  );
}
