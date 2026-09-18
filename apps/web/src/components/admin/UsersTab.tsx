"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { admin as adminApi } from "@/lib/api/endpoints";
import type { AdminUser } from "@/lib/api/types";
import {
  Badge,
  ErrorNote,
  PAGE_SIZE,
  Pager,
  SectionHeader,
  SmallButton,
  StatTile,
  Table,
  TableSkeleton,
  errorText,
  inputClass,
  when,
} from "./ui";

export function UsersTab({ currentAdminId }: { currentAdminId: string }) {
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["admin", "users", q, offset],
    queryFn: () => adminApi.users({ q: q || undefined, limit: PAGE_SIZE, offset }),
  });

  return (
    <div>
      <SectionHeader title="Users" hint="Search, adjust credits, suspend, or grant admin access.">
        <form
          className="flex gap-2"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            setOffset(0);
            setQ(search.trim());
          }}
        >
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Email or name"
            className={`${inputClass} w-56`}
          />
          <SmallButton type="submit" tone="primary">
            Search
          </SmallButton>
          {q && (
            <SmallButton
              onClick={() => {
                setSearch("");
                setQ("");
                setOffset(0);
              }}
            >
              Clear
            </SmallButton>
          )}
        </form>
      </SectionHeader>

      {selectedId && (
        <UserDetailPanel
          userId={selectedId}
          isSelf={selectedId === currentAdminId}
          onClose={() => setSelectedId(null)}
        />
      )}

      {query.isLoading ? (
        <TableSkeleton />
      ) : query.isError || !query.data ? (
        <ErrorNote>{errorText(query.error, "Couldn't load users.")}</ErrorNote>
      ) : (
        <>
          <Table
            columns={["User", "Status", "Credits", "Joined", "Last login", ""]}
            rows={query.data.items.map((u) => [
              <div key="u">
                <p className="font-medium">{u.email}</p>
                {u.full_name && <p className="text-[12px] text-muted">{u.full_name}</p>}
              </div>,
              <UserBadges key="b" user={u} />,
              u.credits_balance,
              when(u.created_at),
              when(u.last_login_at),
              <SmallButton key="m" onClick={() => setSelectedId(u.id)}>
                Manage
              </SmallButton>,
            ])}
            empty={q ? `No users match “${q}”.` : "No users yet."}
          />
          <Pager offset={offset} total={query.data.total} onChange={setOffset} />
        </>
      )}
    </div>
  );
}

function UserBadges({ user }: { user: AdminUser }) {
  return (
    <div className="flex flex-wrap gap-1">
      {user.is_active ? <Badge tone="good">Active</Badge> : <Badge tone="bad">Suspended</Badge>}
      {user.is_admin && <Badge tone="warn">Admin</Badge>}
      {!user.email_verified && <Badge>Unverified</Badge>}
      {user.auth_provider === "google" && <Badge>Google</Badge>}
    </div>
  );
}

function UserDetailPanel({ userId, isSelf, onClose }: { userId: string; isSelf: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const detail = useQuery({ queryKey: ["admin", "user", userId], queryFn: () => adminApi.userDetail(userId) });

  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["admin", "user", userId] });
    qc.invalidateQueries({ queryKey: ["admin", "users"] });
    qc.invalidateQueries({ queryKey: ["admin", "audit"] });
    qc.invalidateQueries({ queryKey: ["admin", "overview"] });
  };

  const update = useMutation({
    mutationFn: (input: { is_active?: boolean; is_admin?: boolean; email_verified?: boolean }) =>
      adminApi.updateUser(userId, input),
    onSuccess: refresh,
  });

  const adjust = useMutation({
    mutationFn: () => adminApi.adjustCredits(userId, { amount: Number(amount), note: note.trim() }),
    onSuccess: () => {
      setAmount("");
      setNote("");
      refresh();
    },
  });

  const amountNum = Number(amount);
  const canAdjust = amount !== "" && Number.isInteger(amountNum) && amountNum !== 0 && note.trim().length >= 3;

  const confirmThen = (message: string, run: () => void) => {
    if (window.confirm(message)) run();
  };

  return (
    <div className="tu-pop mb-6 rounded-[20px] border border-sage/50 bg-sage-tint/20 p-5">
      {detail.isLoading || !detail.data ? (
        detail.isError ? <ErrorNote>{errorText(detail.error, "Couldn't load this user.")}</ErrorNote> : <TableSkeleton />
      ) : (
        <>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-display text-[20px] text-ink">{detail.data.user.email}</p>
              <p className="text-[13px] text-muted">
                {detail.data.user.full_name || "No name"} · joined {when(detail.data.user.created_at)}
              </p>
              <div className="mt-2">
                <UserBadges user={detail.data.user} />
              </div>
            </div>
            <SmallButton onClick={onClose}>Close</SmallButton>
          </div>

          <div className="tu-stagger mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
            <StatTile label="Credits" value={detail.data.user.credits_balance} />
            <StatTile label="Try-ons" value={detail.data.tryon_jobs_total} />
            <StatTile label="Photos" value={detail.data.photos_total} />
            <StatTile label="Wardrobe" value={detail.data.wardrobe_items_total} />
            <StatTile label="Shop clicks" value={detail.data.affiliate_clicks_total} />
          </div>

          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <div className="rounded-[16px] border border-line bg-surface p-4">
              <p className="text-[13px] font-semibold text-ink">Adjust credits</p>
              <p className="mt-0.5 text-[12px] text-muted">
                Positive adds, negative removes. Recorded in the user&rsquo;s credit history and the audit log.
              </p>
              <form
                className="mt-3 flex flex-wrap gap-2"
                onSubmit={(e: FormEvent) => {
                  e.preventDefault();
                  if (!canAdjust) return;
                  const verb = amountNum > 0 ? `Add ${amountNum}` : `Remove ${Math.abs(amountNum)}`;
                  confirmThen(`${verb} credits for ${detail.data!.user.email}?`, () => adjust.mutate());
                }}
              >
                <input
                  type="number"
                  step={1}
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="e.g. 50 or -20"
                  className={`${inputClass} w-32`}
                />
                <input
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Reason (required)"
                  maxLength={200}
                  className={`${inputClass} min-w-0 flex-1`}
                />
                <SmallButton type="submit" tone="primary" disabled={!canAdjust || adjust.isPending}>
                  {adjust.isPending ? "Saving…" : "Apply"}
                </SmallButton>
              </form>
              {adjust.isError && <div className="mt-2"><ErrorNote>{errorText(adjust.error)}</ErrorNote></div>}
            </div>

            <div className="rounded-[16px] border border-line bg-surface p-4">
              <p className="text-[13px] font-semibold text-ink">Account controls</p>
              {isSelf && (
                <p className="mt-0.5 text-[12px] text-muted">This is your own account — you can&rsquo;t suspend or demote yourself.</p>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                {detail.data.user.is_active ? (
                  <SmallButton
                    tone="danger"
                    disabled={isSelf || update.isPending}
                    onClick={() =>
                      confirmThen(
                        `Suspend ${detail.data!.user.email}? They'll be signed out everywhere immediately.`,
                        () => update.mutate({ is_active: false }),
                      )
                    }
                  >
                    Suspend
                  </SmallButton>
                ) : (
                  <SmallButton disabled={update.isPending} onClick={() => update.mutate({ is_active: true })}>
                    Reactivate
                  </SmallButton>
                )}
                {detail.data.user.is_admin ? (
                  <SmallButton
                    tone="danger"
                    disabled={isSelf || update.isPending}
                    onClick={() =>
                      confirmThen(`Remove admin access from ${detail.data!.user.email}?`, () =>
                        update.mutate({ is_admin: false }),
                      )
                    }
                  >
                    Remove admin
                  </SmallButton>
                ) : (
                  <SmallButton
                    disabled={update.isPending}
                    onClick={() =>
                      confirmThen(
                        `Give ${detail.data!.user.email} full admin access? They'll be able to do everything you can.`,
                        () => update.mutate({ is_admin: true }),
                      )
                    }
                  >
                    Make admin
                  </SmallButton>
                )}
                {!detail.data.user.email_verified && (
                  <SmallButton disabled={update.isPending} onClick={() => update.mutate({ email_verified: true })}>
                    Mark email verified
                  </SmallButton>
                )}
              </div>
              {update.isError && <div className="mt-2"><ErrorNote>{errorText(update.error)}</ErrorNote></div>}
            </div>
          </div>

          <p className="mb-2 mt-5 text-[13px] font-semibold text-ink">Recent credit history</p>
          <Table
            columns={["When", "Change", "Balance", "Reason", "Note"]}
            rows={detail.data.recent_transactions.map((t) => [
              when(t.created_at),
              <span key="a" className={t.amount < 0 ? "text-[#a4553f]" : "text-sage-deep"}>
                {t.amount > 0 ? `+${t.amount}` : t.amount}
              </span>,
              t.balance_after,
              t.reason.replaceAll("_", " "),
              t.note ?? "—",
            ])}
            empty="No credit activity yet."
          />
        </>
      )}
    </div>
  );
}
