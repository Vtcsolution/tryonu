"use client";

import { payWays, useCheckoutProvider } from "@/lib/useCheckout";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { AccountSettings } from "@/components/account/AccountSettings";
import { AdminShell, type NavGroup, type ShellArea } from "@/components/admin/AdminShell";
import { Badge, ErrorNote, SmallButton, errorText, inputClass, money } from "@/components/admin/ui";
import { DeveloperDocs, WidgetSteps } from "@/components/developers/DeveloperDocs";
import { DevChrome } from "@/components/developers/DevChrome";
import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api/client";
import { developers as devApi } from "@/lib/api/endpoints";
import type { DeveloperAccount, DeveloperApiKeyCreated, User } from "@/lib/api/types";
import { useSession } from "@/lib/auth/useSession";

const ACCOUNT_KEY = ["developers", "me"];

/** The Developer API portal: sign up, keys, credits, usage, docs. Kept apart from the shop and the store panel. */
export function DeveloperPortal() {
  const router = useRouter();
  const { user, isLoading } = useSession();
  useEffect(() => {
    if (!isLoading && !user) router.replace("/developers/sign-up");
  }, [isLoading, user, router]);

  const account = useQuery({
    queryKey: ACCOUNT_KEY,
    queryFn: async () => {
      try {
        return await devApi.mine();
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
    enabled: !!user,
    staleTime: 0,
    refetchOnWindowFocus: true,
  });

  if (isLoading || !user || account.isLoading) {
    return (
      <div className="grid min-h-screen place-items-center bg-paper">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
      </div>
    );
  }
  if (account.isError) {
    return (
      <DevChrome>
        <section className="mx-auto w-[min(900px,calc(100%-42px))] py-16">
          <ErrorNote>{errorText(account.error, "Couldn't load your developer account.")}</ErrorNote>
        </section>
      </DevChrome>
    );
  }
  if (!account.data) {
    return (
      <DevChrome>
        <OpenDeveloperAccount />
      </DevChrome>
    );
  }
  return <Portal account={account.data} user={user} />;
}

function OpenDeveloperAccount() {
  const qc = useQueryClient();
  const [company, setCompany] = useState("");
  const [website, setWebsite] = useState("");
  const open = useMutation({
    mutationFn: () => devApi.open({ company_name: company.trim(), website: website.trim() || null }),
    onSuccess: (a) => qc.setQueryData(ACCOUNT_KEY, a),
  });
  return (
    <section className="mx-auto w-[min(640px,calc(100%-42px))] py-14 md:py-20">
      <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">TryOnU for developers</p>
      <h1 className="mt-2 font-display text-[clamp(30px,4.5vw,42px)] leading-tight text-ink">Set up your developer account</h1>
      <p className="mt-3 text-[16px] text-muted">
        Add TryOnU&apos;s virtual try-on to your own shop or app. You pay only for the try-ons you use.
      </p>
      <form
        className="mt-6 space-y-4 rounded-[24px] border border-line bg-surface p-6"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          if (company.trim().length >= 2) open.mutate();
        }}
      >
        <label className="block">
          <span className="mb-1.5 block text-[14px] font-medium text-ink-soft">Company or project name</span>
          <input value={company} onChange={(e) => setCompany(e.target.value)} maxLength={120} autoFocus className={`${inputClass} w-full`} />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-[14px] font-medium text-ink-soft">Website (optional)</span>
          <input value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="https://" className={`${inputClass} w-full`} />
        </label>
        {open.isError && <ErrorNote>{errorText(open.error)}</ErrorNote>}
        <Button type="submit" size="md" disabled={open.isPending || company.trim().length < 2}>
          {open.isPending ? "Creating…" : "Create developer account"} <span aria-hidden="true">→</span>
        </Button>
      </form>
    </section>
  );
}

type Tab = "overview" | "keys" | "credits" | "usage" | "payments" | "docs" | "account";

const NAV: readonly NavGroup<Tab>[] = [
  {
    group: "API",
    tabs: [
      { id: "overview", label: "Overview", icon: "overview" },
      { id: "keys", label: "API keys", icon: "settings" },
      { id: "usage", label: "Usage", icon: "tryons" },
      { id: "docs", label: "Docs & code", icon: "audit" },
    ],
  },
  {
    group: "Billing",
    tabs: [
      { id: "credits", label: "Buy credits", icon: "packs" },
      { id: "payments", label: "Payments", icon: "payments" },
    ],
  },
  { group: "You", tabs: [{ id: "account", label: "My account", icon: "users" }] },
];
const TAB_IDS = new Set<string>(NAV.flatMap((g) => g.tabs.map((t) => t.id)));
const AREA: ShellArea = { name: "Developers", home: "/developers/console", role: "Developer" };

function Portal({ account, user }: { account: DeveloperAccount; user: User }) {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("overview");
  const [drawerOpen, setDrawerOpen] = useState(false);
  useEffect(() => {
    const read = () => {
      const hash = window.location.hash.slice(1);
      setTab(TAB_IDS.has(hash) ? (hash as Tab) : "overview");
    };
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);
  const go = useCallback(
    (next: Tab) => {
      setTab(next);
      window.history.replaceState(null, "", `${window.location.pathname}#${next}`);
      window.scrollTo({ top: 0 });
      qc.invalidateQueries({ queryKey: ACCOUNT_KEY });
    },
    [qc],
  );

  return (
    <AdminShell nav={NAV} active={tab} onSelect={go} email={user.email} drawerOpen={drawerOpen} setDrawerOpen={setDrawerOpen} area={AREA}>
      <div className="space-y-6">
        {account.status !== "active" && (
          <ErrorNote>This developer account is suspended, so API calls are refused. Please contact TryOnU.</ErrorNote>
        )}
        {tab === "overview" && <Overview account={account} go={go} />}
        {tab === "keys" && <Keys />}
        {tab === "credits" && <BuyCredits account={account} />}
        {tab === "usage" && <Usage />}
        {tab === "payments" && <Payments />}
        {tab === "docs" && <DeveloperDocs />}
        {tab === "account" && <AccountSettings user={user} />}
      </div>
    </AdminShell>
  );
}

function Card({ title, hint, children }: { title: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-[24px] border border-line bg-surface p-6">
      <h2 className="font-display text-[22px] text-ink">{title}</h2>
      {hint && <p className="mt-1 text-[14px] text-muted">{hint}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Overview({ account, go }: { account: DeveloperAccount; go: (t: Tab) => void }) {
  const keys = useQuery({ queryKey: ["developers", "keys"], queryFn: devApi.keys });
  const hasKey = (keys.data ?? []).some((k) => !k.revoked_at);
  const steps: { done: boolean; title: string; text: string; tab: Tab; action: string }[] = [
    { done: hasKey, title: "Create a key", text: "A website key for the \u201cTry it on\u201d button, or a secret key for your server.", tab: "keys", action: "Create a key" },
    { done: account.credits > 0, title: "Buy credits", text: "1 credit = 1 try-on. They never expire.", tab: "credits", action: "Buy credits" },
    { done: account.tryons_total > 0, title: "Add it to your shop", text: "Shopify, WordPress or any website: copy and paste.", tab: "docs", action: "Show me how" },
  ];
  return (
    <>
      <section className="rounded-[24px] border border-line bg-surface p-6">
        <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">TryOnU try-on API</p>
        <h1 className="mt-1 font-display text-[30px] leading-tight text-ink">{account.company_name}</h1>
        <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Stat label="Credits left" value={account.credits.toLocaleString()} note="1 credit = 1 try-on" warn={account.credits < 5} />
          <Stat label="Try-ons, last 30 days" value={account.tryons_30d.toLocaleString()} />
          <Stat label="Try-ons, all time" value={account.tryons_total.toLocaleString()} />
        </div>
      </section>
      <Card title="Get started">
        <ol className="grid gap-3 md:grid-cols-3">
          {steps.map((s, i) => (
            <li key={s.title} className={`rounded-[16px] border p-4 ${s.done ? "border-sage/40 bg-sage-tint/30" : "border-line"}`}>
              <span
                className={`grid h-8 w-8 place-items-center rounded-full text-[14px] font-semibold ${s.done ? "bg-sage text-white" : "border border-line-strong text-ink-soft"}`}
                aria-hidden="true"
              >
                {s.done ? "✓" : i + 1}
              </span>
              <p className="mt-2 text-[16px] font-semibold text-ink">{s.title}</p>
              <p className="mt-0.5 text-[14px] text-muted">{s.text}</p>
              {!s.done && (
                <button
                  type="button"
                  onClick={() => go(s.tab)}
                  className="tu-press mt-3 inline-flex min-h-[40px] items-center rounded-full bg-sage px-4 text-[14px] font-semibold text-white hover:bg-sage-deep"
                >
                  {s.action} →
                </button>
              )}
            </li>
          ))}
        </ol>
      </Card>
    </>
  );
}

function Stat({ label, value, note, warn }: { label: string; value: string; note?: string; warn?: boolean }) {
  return (
    <div className={`rounded-[18px] border p-4 ${warn ? "border-[#c9a13b]/50 bg-[#c9a13b]/10" : "border-line bg-paper-2/40"}`}>
      <p className="text-[12px] uppercase tracking-[0.08em] text-faint">{label}</p>
      <p className="mt-1 font-display text-[30px] text-ink">{value}</p>
      {note && <p className="text-[13px] text-muted">{note}</p>}
    </div>
  );
}

function Keys() {
  const qc = useQueryClient();
  const keys = useQuery({ queryKey: ["developers", "keys"], queryFn: devApi.keys });
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"public" | "secret">("public");
  const [domains, setDomains] = useState("");
  const [fresh, setFresh] = useState<DeveloperApiKeyCreated | null>(null);
  const [copied, setCopied] = useState(false);
  const [confirm, setConfirm] = useState<string | null>(null);
  const make = useMutation({
    mutationFn: () =>
      devApi.makeKey({
        name: name.trim() || (kind === "public" ? "My website" : "My server"),
        kind,
        allowed_domains: kind === "public" ? domains.split(/[\s,]+/).filter(Boolean) : [],
      }),
    onSuccess: (k) => {
      setFresh(k);
      setName("");
      setDomains("");
      setCopied(false);
      qc.invalidateQueries({ queryKey: ["developers", "keys"] });
    },
  });
  const revoke = useMutation({
    mutationFn: (id: string) => devApi.revokeKey(id),
    onSuccess: () => {
      setConfirm(null);
      qc.invalidateQueries({ queryKey: ["developers", "keys"] });
    },
  });
  return (
    <>
      <Card title="Create a key" hint="One key per website or server, so you can turn one off alone.">
        <div role="radiogroup" aria-label="Key type" className="mb-4 grid gap-2 sm:grid-cols-2">
          {(
            [
              ["public", "Website key", "For the \u201cTry it on\u201d button on your shop. Works only on your website."],
              ["secret", "Secret server key", "For your server only. Never put it in a web page."],
            ] as const
          ).map(([id, title, text]) => (
            <button
              key={id}
              type="button"
              role="radio"
              aria-checked={kind === id}
              onClick={() => setKind(id)}
              className={`rounded-[16px] border p-4 text-left ${kind === id ? "border-sage bg-sage-tint/30" : "border-line hover:border-line-strong"}`}
            >
              <span className="text-[15.5px] font-semibold text-ink">{kind === id ? "● " : "○ "}{title}</span>
              <span className="mt-1 block text-[13.5px] text-muted">{text}</span>
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {kind === "public" && (
            <input
              value={domains}
              onChange={(e) => setDomains(e.target.value)}
              placeholder="Your shop's address, e.g. yourshop.com"
              aria-label="Your shop's web address (several: separate with commas)"
              className={`${inputClass} w-full sm:w-80`}
            />
          )}
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={kind === "public" ? "Name, e.g. My shop" : "Name, e.g. My shop server"}
            maxLength={80}
            className={`${inputClass} w-full sm:w-64`}
          />
          <SmallButton tone="primary" disabled={make.isPending} onClick={() => make.mutate()}>
            {make.isPending ? "Creating…" : "+ Create key"}
          </SmallButton>
        </div>
        {make.isError && <div className="mt-3"><ErrorNote>{errorText(make.error)}</ErrorNote></div>}
        {fresh && (
          <div className="mt-4 rounded-[16px] border border-[#c9a13b]/50 bg-[#c9a13b]/10 p-4">
            <p className="text-[15px] font-semibold text-ink">Copy your key now: it is shown only once.</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <code className="break-all rounded-lg bg-paper-2 px-3 py-2 text-[14px] text-ink">{fresh.key}</code>
              <SmallButton
                tone="primary"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(fresh.key);
                    setCopied(true);
                  } catch {
                    setCopied(false);
                  }
                }}
              >
                {copied ? "✓ Copied" : "Copy"}
              </SmallButton>
            </div>
            {fresh.kind === "public" ? (
              <>
                <p className="mt-2 text-[13.5px] text-ink-soft">
                  This website key is safe in your web page: it only works on {(fresh.allowed_domains ?? []).join(", ")}. Now add the
                  button to your shop:
                </p>
                <WidgetSteps shop="website" websiteKey={fresh.key} />
                <p className="mt-2 text-[13.5px] text-muted">Shopify or WordPress? See the steps in <b>Docs &amp; code</b>.</p>
              </>
            ) : (
              <p className="mt-2 text-[13.5px] text-ink-soft">
                Keep it on your server only. If someone else gets it, delete it below and make a new one.
              </p>
            )}
            <SmallButton onClick={() => setFresh(null)}>I&apos;ve saved it</SmallButton>
          </div>
        )}
      </Card>
      <Card title="Your keys">
        {keys.isLoading ? (
          <p className="text-[14px] text-muted">Loading…</p>
        ) : !keys.data || keys.data.length === 0 ? (
          <p className="text-[14px] text-muted">No keys yet.</p>
        ) : (
          <div className="divide-y divide-line rounded-[16px] border border-line">
            {keys.data.map((k) => (
              <div key={k.id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-[14px]">
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-ink">
                    {k.name}{" "}
                    <span className="text-[12.5px] font-normal text-muted">
                      {k.kind === "public" ? `· Website key for ${(k.allowed_domains ?? []).join(", ")}` : "· Secret server key"}
                    </span>
                  </p>
                  <p className="text-[13px] text-muted">
                    <code>{k.prefix}…</code> · created {new Date(k.created_at).toLocaleDateString()}
                    {k.last_used_at ? ` · last used ${new Date(k.last_used_at).toLocaleString()}` : " · never used"}
                  </p>
                </div>
                {k.revoked_at ? (
                  <Badge tone="bad">Revoked</Badge>
                ) : confirm === k.id ? (
                  <>
                    <SmallButton tone="danger" disabled={revoke.isPending} onClick={() => revoke.mutate(k.id)}>
                      Yes, revoke
                    </SmallButton>
                    <SmallButton onClick={() => setConfirm(null)}>Cancel</SmallButton>
                  </>
                ) : (
                  <>
                    <Badge tone="good">Active</Badge>
                    <SmallButton tone="danger" onClick={() => setConfirm(k.id)}>Revoke</SmallButton>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}

function BuyCredits({ account }: { account: DeveloperAccount }) {
  const packs = useQuery({ queryKey: ["developers", "packs"], queryFn: devApi.packs });
  const qc = useQueryClient();
  const checkoutProvider = useCheckoutProvider();
  const buy = useMutation({
    mutationFn: (code: string) => devApi.buyPack(code),
    onSuccess: (res) => {
      if (res.checkout_url) window.location.assign(res.checkout_url);
      else qc.invalidateQueries({ queryKey: ACCOUNT_KEY });
    },
  });
  return (
    <Card
      title="Buy credits"
      hint={`You have ${account.credits.toLocaleString()} credits. 1 credit = 1 try-on. They never expire. Pay by ${payWays(checkoutProvider)}.`}
    >
      {packs.isLoading ? (
        <p className="text-[14px] text-muted">Loading…</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          {(packs.data ?? []).map((p) => (
            <div key={p.id} className="flex flex-col rounded-[20px] border border-line p-5">
              <p className="font-display text-[22px] text-ink">{p.name}</p>
              <p className="mt-1 text-[30px] font-semibold text-ink">{money(p.price_cents, p.currency)}</p>
              <p className="text-[15px] text-ink-soft">{p.tryons.toLocaleString()} try-ons</p>
              <p className="text-[13.5px] text-muted">{money(Math.round(p.price_cents / p.tryons), p.currency)} per try-on</p>
              <div className="mt-4">
                <Button size="md" className="w-full" disabled={buy.isPending} onClick={() => buy.mutate(p.code)}>
                  {buy.isPending && buy.variables === p.code ? "Opening checkout…" : `Buy ${p.name}`}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
      {buy.isError && <div className="mt-3"><ErrorNote>{errorText(buy.error)}</ErrorNote></div>}
    </Card>
  );
}

const STATUS_TONE: Record<string, "good" | "bad" | "warn" | "neutral"> = {
  completed: "good",
  failed: "bad",
  queued: "warn",
  processing: "warn",
};

function Usage() {
  const usage = useQuery({ queryKey: ["developers", "usage"], queryFn: devApi.usage, refetchInterval: 15_000 });
  return (
    <Card title="Usage" hint="Every try-on, newest first. Failed ones cost 0.">
      {usage.isLoading ? (
        <p className="text-[14px] text-muted">Loading…</p>
      ) : !usage.data || usage.data.length === 0 ? (
        <p className="text-[14px] text-muted">No try-ons yet. See Docs & code to make your first one.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-[14px]">
            <thead>
              <tr className="border-b border-line text-[12px] uppercase tracking-[0.08em] text-faint">
                <th className="py-2 pr-3 font-medium">When</th>
                <th className="py-2 pr-3 font-medium">Try-on id</th>
                <th className="py-2 pr-3 font-medium">Your reference</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 font-medium">Credits</th>
                <th className="py-2 font-medium">Result</th>
              </tr>
            </thead>
            <tbody>
              {usage.data.map((u) => (
                <tr key={u.id} className="border-b border-line last:border-0">
                  <td className="py-2.5 pr-3 text-ink-soft">{new Date(u.created_at).toLocaleString()}</td>
                  <td className="py-2.5 pr-3 font-mono text-[12.5px] text-ink-soft">{u.id.slice(0, 8)}…</td>
                  <td className="py-2.5 pr-3 text-ink-soft">{u.reference ?? "—"}</td>
                  <td className="py-2.5 pr-3">
                    <Badge tone={STATUS_TONE[u.status] ?? "neutral"}>{u.status}</Badge>
                    {u.error && <p className="mt-1 max-w-xs text-[12.5px] text-muted">{u.error.slice(0, 120)}</p>}
                  </td>
                  <td className="py-2.5 pr-3 text-ink">{u.refunded ? 0 : u.credits}</td>
                  <td className="py-2.5">
                    {u.result_image_url ? (
                      <a href={u.result_image_url} target="_blank" rel="noopener noreferrer" className="font-medium text-sage-deep hover:underline">
                        View picture ↗
                      </a>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function Payments() {
  const payments = useQuery({ queryKey: ["developers", "payments"], queryFn: devApi.payments });
  return (
    <Card title="Payments">
      {!payments.data || payments.data.length === 0 ? (
        <p className="text-[14px] text-muted">No payments yet.</p>
      ) : (
        <div className="divide-y divide-line rounded-[16px] border border-line">
          {payments.data.map((p) => (
            <div key={p.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-[14px]">
              <span className="text-ink-soft">
                {p.pack_name ?? "Pack"} · {p.tryons ?? "?"} try-ons · {new Date(p.created_at).toLocaleDateString()}
              </span>
              <span className="flex items-center gap-2">
                <span className="font-semibold text-ink">{money(p.amount_cents, p.currency)}</span>
                <Badge tone={p.status === "succeeded" ? "good" : p.status === "failed" ? "bad" : "neutral"}>
                  {p.status === "succeeded" ? "Paid" : p.status === "pending" ? "Not finished" : p.status}
                </Badge>
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
