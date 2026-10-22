"use client";

import { payWays, useCheckoutProvider } from "@/lib/useCheckout";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AccountSettings } from "@/components/account/AccountSettings";
import { AdminShell, Icon, type NavGroup, type ShellArea } from "@/components/admin/AdminShell";
import { Badge, ErrorNote, SmallButton, errorText, inputClass } from "@/components/admin/ui";
import { SiteChrome } from "@/components/layout/SiteChrome";
import { ShopperTryOns } from "@/components/business/ShopperTryOns";
import { CountryPicker } from "@/components/ui/CountryPicker";
import { Button } from "@/components/ui/Button";
import { formatPrice } from "@/components/try/shop";
import { ApiError } from "@/lib/api/client";
import { credits as creditsApi, preferences as preferencesApi, stores as storesApi } from "@/lib/api/endpoints";
import type { Store, StoreDelivery, StorePlan, StoreProduct, StoreProductInput, User } from "@/lib/api/types";
import { useSession } from "@/lib/auth/useSession";
import { countryFlag, countryName, deliveryText } from "@/lib/countries";

const STORE_KEY = ["business", "store"];

/** A company's own area: open a store, unlock a plan, list products, connect a feed. */
export function BusinessDashboard() {
  const router = useRouter();
  const { user, isLoading } = useSession();

  useEffect(() => {
    if (!isLoading && !user) router.replace("/business/sign-up");
  }, [isLoading, user, router]);

  const storeQuery = useQuery({
    queryKey: STORE_KEY,
    queryFn: async () => {
      try {
        return await storesApi.mine();
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
    enabled: !!user,
    // a plan or approval can change from the admin side at any time
    staleTime: 0,
    refetchOnWindowFocus: true,
  });

  if (isLoading || !user || storeQuery.isLoading) {
    return (
      <div className="grid min-h-screen place-items-center bg-paper">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
      </div>
    );
  }
  if (storeQuery.isError) {
    return (
      <SiteChrome>
        <section className="mx-auto w-[min(1100px,calc(100%-32px))] py-16">
          <ErrorNote>{errorText(storeQuery.error, "Couldn't load your store.")}</ErrorNote>
        </section>
      </SiteChrome>
    );
  }
  const store = storeQuery.data;
  if (!store) {
    return (
      <SiteChrome>
        <section className="mx-auto w-[min(1100px,calc(100%-32px))] py-12 md:py-16">
          <OpenStore />
        </section>
      </SiteChrome>
    );
  }
  return <StorePanel store={store} user={user} />;
}

// ------------------------------------------------------------------ open a store

/** Right after a store account is made: two short steps, then the store panel. */
function OpenStore() {
  const qc = useQueryClient();
  const prefs = useQuery({ queryKey: ["preferences"], queryFn: preferencesApi.get });
  const [step, setStep] = useState<1 | 2>(1);
  const [name, setName] = useState("");
  const [country, setCountry] = useState<string | null>(null); // null: the account's country
  const [website, setWebsite] = useState("");
  const [description, setDescription] = useState("");
  const [more, setMore] = useState(false);
  const [mode, setMode] = useState<StoreDelivery>("domestic");
  const [countries, setCountries] = useState<string[]>([]);
  const home = country ?? prefs.data?.country ?? "";

  const create = useMutation({
    mutationFn: async () => {
      let store = await storesApi.create({
        name: name.trim(),
        country: home,
        website_url: website.trim() || undefined,
        description: description.trim() || undefined,
      });
      if (mode !== "domestic") {
        store = await storesApi.update({ delivery: mode, delivery_countries: mode === "countries" ? countries : [] });
      }
      return store;
    },
    onSuccess: (store) => qc.setQueryData(STORE_KEY, store),
  });
  const stepOneDone = name.trim().length >= 2 && !!home;

  return (
    <div className="mx-auto max-w-2xl">
      <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-sage-deep">Your store account is ready</p>
      <h1 className="mt-2 font-display text-[clamp(28px,4.5vw,40px)] leading-tight text-ink">Set up your store</h1>
      <p className="mt-2 text-[16px] text-muted">Two quick steps. You can change everything later.</p>

      {/* progress */}
      <ol className="mt-6 flex items-center gap-3 text-[15px]" aria-label="Steps">
        {[
          [1, "Your store"],
          [2, "Delivery"],
        ].map(([n, label]) => (
          <li key={n} className="flex items-center gap-2" aria-current={step === n ? "step" : undefined}>
            <span
              className={`grid h-8 w-8 place-items-center rounded-full text-[14px] font-semibold ${
                step === n ? "bg-sage text-white" : step > (n as number) ? "bg-sage/30 text-sage-deep" : "border border-line-strong text-muted"
              }`}
            >
              {step > (n as number) ? "✓" : n}
            </span>
            <span className={step === n ? "font-semibold text-ink" : "text-muted"}>{label}</span>
            {n === 1 && <span className="mx-1 h-px w-8 bg-line-strong" aria-hidden="true" />}
          </li>
        ))}
      </ol>

      <form
        className="mt-6 space-y-5 rounded-[24px] border border-line bg-surface p-6"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          if (step === 1 && stepOneDone) setStep(2);
          else if (step === 2 && !(mode === "countries" && countries.length === 0)) create.mutate();
        }}
      >
        {step === 1 ? (
          <>
            <Field label="Store name" hint="Shoppers see this name on every product.">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={120}
                autoFocus
                placeholder="e.g. Lahore Couture"
                className={`${inputClass} w-full`}
                required
              />
            </Field>
            <Field label="Your store's country" hint="Shoppers in this country see your products first.">
              <CountrySelect value={home} onChange={setCountry} />
            </Field>
            {more ? (
              <>
                <Field label="Your website (optional)">
                  <input value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="https://" className={`${inputClass} w-full`} />
                </Field>
                <Field label="About your store (optional)">
                  <textarea value={description} onChange={(e) => setDescription(e.target.value)} maxLength={2000} rows={3} className={`${inputClass} h-auto w-full py-2`} />
                </Field>
              </>
            ) : (
              <button type="button" onClick={() => setMore(true)} className="text-[15px] font-medium text-sage-deep hover:underline">
                + Add your website and a short description (optional)
              </button>
            )}
            <Button type="submit" size="md" disabled={!stepOneDone}>
              Next: delivery <span aria-hidden="true">→</span>
            </Button>
          </>
        ) : (
          <>
            <div>
              <p className="text-[16px] font-semibold text-ink">Where do you deliver?</p>
              <p className="mt-1 text-[14.5px] text-muted">Shoppers only see your products if you can deliver to them.</p>
            </div>
            <DeliveryChooser home={home} mode={mode} onMode={setMode} countries={countries} onCountries={setCountries} />
            {create.isError && <ErrorNote>{errorText(create.error)}</ErrorNote>}
            <div className="flex flex-wrap items-center gap-3">
              <Button type="submit" size="md" disabled={create.isPending || (mode === "countries" && countries.length === 0)}>
                {create.isPending ? "Opening…" : "Open my store"} {!create.isPending && <span aria-hidden="true">→</span>}
              </Button>
              <button type="button" onClick={() => setStep(1)} className="text-[15px] text-muted hover:text-ink">
                ← Back
              </button>
            </div>
          </>
        )}
      </form>
      <p className="mt-4 text-center text-[14px] text-muted">
        Next: we approve your store (usually within a day), you pick a plan and add products.
      </p>
    </div>
  );
}

// ------------------------------------------------------------------- dashboard

// ------------------------------------------------------------------ store panel

type Tab = "overview" | "info" | "tryons" | "products" | "import" | "profile" | "plan" | "payments" | "account";

const NAV: readonly NavGroup<Tab>[] = [
  {
    group: "My store",
    tabs: [
      { id: "overview", label: "Overview", icon: "overview" },
      { id: "products", label: "Products", icon: "products" },
      { id: "import", label: "Add from a file", icon: "upload" },
      { id: "tryons", label: "Customer try-ons", icon: "tryons" },
      { id: "info", label: "Store summary", icon: "audit" },
      { id: "profile", label: "Edit store", icon: "retailers" },
    ],
  },
  {
    group: "Billing",
    tabs: [
      { id: "plan", label: "My plan", icon: "packs" },
      { id: "payments", label: "Payments", icon: "payments" },
    ],
  },
  {
    group: "You",
    tabs: [{ id: "account", label: "My account", icon: "users" }],
  },
];
const TAB_IDS = new Set<string>(NAV.flatMap((g) => g.tabs.map((t) => t.id)));
const labelFor = (tab: Tab) => NAV.flatMap((g) => g.tabs).find((t) => t.id === tab)?.label ?? "";
const STORE_AREA: ShellArea = { name: "Store", home: "/business", role: "Store owner" };

function tabFromLocation(): Tab {
  if (typeof window === "undefined") return "overview";
  // back from PayPal: the Plan page confirms the subscription
  if (new URLSearchParams(window.location.search).has("subscription")) return "plan";
  const hash = window.location.hash.slice(1);
  return TAB_IDS.has(hash) ? (hash as Tab) : "overview";
}

/** A company's store panel: a sidebar like the admin panel, one page per task. */
function StorePanel({ store, user }: { store: Store; user: User }) {
  const [tab, setTab] = useState<Tab>("overview");
  const [drawerOpen, setDrawerOpen] = useState(false);

  // the page lives in the URL hash (/business#products), so refresh and links keep it
  useEffect(() => {
    setTab(tabFromLocation());
    const onHash = () => setTab(tabFromLocation());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    document.title = `${labelFor(tab)} · ${store.name} · TryOnU`;
  }, [tab, store.name]);

  const qc = useQueryClient();
  const go = useCallback(
    (next: Tab) => {
      setTab(next);
      window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#${next}`);
      window.scrollTo({ top: 0 });
      // each page shows the store as it is now (e.g. a plan TryOnU just gave)
      qc.invalidateQueries({ queryKey: STORE_KEY });
    },
    [qc],
  );

  return (
    <AdminShell
      nav={NAV}
      active={tab}
      onSelect={go}
      email={user.email}
      drawerOpen={drawerOpen}
      setDrawerOpen={setDrawerOpen}
      area={STORE_AREA}
      headerExtra={
        store.live ? (
          <a
            href={`/stores/${store.slug}`}
            target="_blank"
            rel="noopener"
            className="tu-press hidden h-9 items-center gap-1.5 rounded-full border border-sage/50 px-3.5 text-[13.5px] font-medium text-sage-deep hover:bg-sage-tint/50 sm:inline-flex"
          >
            <Icon name="external" size={15} />
            My store page
          </a>
        ) : null
      }
    >
      <div className="space-y-6">
        {tab === "overview" && (
          <>
            <StoreHeader store={store} />
            <NextSteps store={store} go={go} />
            <StatsSection />
          </>
        )}
        {tab === "info" && <StoreInfo store={store} email={user.email} go={go} />}
        {tab === "tryons" && <ShopperTryOns store={store} onBuyMore={() => go("plan")} />}
        {tab === "products" && (store.plan_active ? <ProductsSection store={store} /> : <NeedsPlan go={go} what="add products" />)}
        {tab === "import" && (store.plan_active ? <FeedSection store={store} /> : <NeedsPlan go={go} what="import products" />)}
        {tab === "profile" && <ProfileSection store={store} />}
        {tab === "plan" && <PlansSection store={store} />}
        {tab === "payments" && <PaymentsSection go={go} />}
        {tab === "account" && <AccountSettings user={user} />}
      </div>
    </AdminShell>
  );
}

const DAY_MS = 86_400_000;

/** Everything about the store in one place, each with where to change it. */
function StoreInfo({ store, email, go }: { store: Store; email: string; go: (tab: Tab) => void }) {
  const status = STATUS[store.status] ?? STATUS.pending;
  const ends = store.plan_expires_at ? new Date(store.plan_expires_at) : null;
  const daysLeft = ends ? Math.max(0, Math.ceil((ends.getTime() - Date.now()) / DAY_MS)) : 0;
  const planName = (store.plan_code ?? "").replace(/^./, (c) => c.toUpperCase());
  const notLiveWhy =
    store.status !== "approved" ? "waiting for TryOnU's approval" : !store.plan_active ? "no active plan" : "";
  const rows: { label: string; value: ReactNode; tab?: Tab; action?: string }[] = [
    { label: "Store name", value: store.name, tab: "profile", action: "Change" },
    {
      label: "Country",
      value: (
        <>
          <span className="mr-1.5 text-[18px]" aria-hidden="true">{countryFlag(store.country)}</span>
          {countryName(store.country)}
          <span className="block text-[13.5px] text-muted">Shoppers in {countryName(store.country)} see your products first.</span>
        </>
      ),
      tab: "profile",
      action: "Change",
    },
    {
      label: "Delivers to",
      value: (
        <>
          🚚 {deliveryText(store.delivery, store.delivery_countries, store.country)}
          <span className="block text-[13.5px] text-muted">Shoppers elsewhere don&apos;t see your products.</span>
        </>
      ),
      tab: "profile",
      action: "Change",
    },
    {
      label: "Status",
      value: (
        <span className="flex flex-wrap items-center gap-2">
          <Badge tone={status.tone}>{status.label}</Badge>
          <Badge tone={store.live ? "good" : "neutral"}>{store.live ? "Live: shoppers can find you" : `Not live: ${notLiveWhy}`}</Badge>
        </span>
      ),
    },
    {
      label: "Your store page",
      value: store.live ? (
        <a href={`/stores/${store.slug}`} target="_blank" rel="noopener" className="font-medium text-sage-deep hover:underline">
          tryonu.app/stores/{store.slug} ↗
        </a>
      ) : (
        <span className="text-muted">tryonu.app/stores/{store.slug} (opens once you&apos;re live)</span>
      ),
    },
    {
      label: "Plan",
      value: store.plan_active ? (
        <>
          {planName}
          {store.plan_free ? " · free from TryOnU" : ""}
          <span className="block text-[13.5px] text-muted">
            Ends {ends?.toLocaleDateString()} · {daysLeft === 1 ? "1 day left" : `${daysLeft} days left`}
            {store.auto_renew ? " · renews automatically" : ""}
          </span>
        </>
      ) : (
        <span className="text-muted">No plan yet</span>
      ),
      tab: "plan",
      action: store.plan_active ? "Renew or upgrade" : "Choose a plan",
    },
    {
      label: "Products",
      value: store.plan_active
        ? `${store.product_count} of ${store.plan_product_limit.toLocaleString()} used · ${Math.max(0, store.plan_product_limit - store.product_count).toLocaleString()} left`
        : `${store.product_count} (a plan sets your limit)`,
      tab: "products",
      action: "Manage",
    },
    {
      label: "Try-on credits",
      value: (
        <>
          🎁 {store.tryon_credits ?? 0} left
          <span className="block text-[13.5px] text-muted">Each one pays for a shopper trying on your product.</span>
        </>
      ),
      tab: "tryons",
      action: "See try-ons",
    },
    {
      label: "Featured",
      value: `★ ${store.featured_count ?? 0} of ${store.plan_featured_limit ?? 0}`,
      tab: "products",
      action: "Manage",
    },
    {
      label: "Product feed",
      value: store.feed_url ? (
        <>
          Connected
          {store.feed_last_result && <span className="block text-[13.5px] text-muted">Last import: {store.feed_last_result}</span>}
        </>
      ) : (
        <span className="text-muted">Not connected</span>
      ),
      tab: "import",
      action: store.feed_url ? "Change" : "Connect",
    },
    { label: "Website", value: store.website_url ?? <span className="text-muted">Not added</span>, tab: "profile", action: "Change" },
    { label: "Contact email", value: store.contact_email ?? <span className="text-muted">Not added</span>, tab: "profile", action: "Change" },
    { label: "WhatsApp", value: store.whatsapp ? `+${store.whatsapp}` : <span className="text-muted">Not added</span>, tab: "profile", action: store.whatsapp ? "Change" : "Add" },
    { label: "Sign-in email", value: email, tab: "account", action: "Change password" },
    { label: "Opened on TryOnU", value: store.opened_at ? new Date(store.opened_at).toLocaleDateString() : "—" },
  ];
  return (
    <section className="rounded-[24px] border border-line bg-surface p-6">
      <div className="flex flex-wrap items-center gap-4">
        {store.logo_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={store.logo_url} alt="" className="h-16 w-16 rounded-[16px] border border-line object-cover" />
        ) : (
          <div className="grid h-16 w-16 place-items-center rounded-[16px] bg-sage text-[26px] font-semibold text-white">
            {store.name.slice(0, 1).toUpperCase()}
          </div>
        )}
        <div>
          <h2 className="font-display text-[26px] leading-tight text-ink">{store.name}</h2>
          <p className="text-[15px] text-muted">
            {countryFlag(store.country)} {countryName(store.country)} · Store on TryOnU
          </p>
        </div>
      </div>
      <dl className="mt-6 divide-y divide-line rounded-[18px] border border-line">
        {rows.map((row) => (
          <div key={row.label} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3.5 sm:flex-nowrap">
            <dt className="w-full text-[14px] font-medium text-muted sm:w-44 sm:shrink-0">{row.label}</dt>
            <dd className="min-w-0 flex-1 text-[16px] text-ink">{row.value}</dd>
            {row.tab && row.action && (
              <button
                type="button"
                onClick={() => go(row.tab!)}
                className="tu-press min-h-[36px] shrink-0 rounded-full border border-line-strong px-3.5 text-[14px] font-medium text-ink hover:border-ink/40"
              >
                {row.action}
              </button>
            )}
          </div>
        ))}
      </dl>
    </section>
  );
}

/** What the current plan gives the store, used and left, in three bars. */
function PlanAllowance({ store }: { store: Store }) {
  const name = (store.plan_code ?? "").replace(/^./, (c) => c.toUpperCase());
  const ends = store.plan_expires_at ? new Date(store.plan_expires_at).toLocaleDateString() : "";
  const bars: { label: string; used: number; total: number; text: string }[] = [
    {
      label: "Products",
      used: store.product_count,
      total: store.plan_product_limit,
      text: `${store.product_count} of ${store.plan_product_limit.toLocaleString()} used`,
    },
    {
      label: "★ Featured products",
      used: store.featured_count ?? 0,
      total: store.plan_featured_limit ?? 0,
      text: `${store.featured_count ?? 0} of ${store.plan_featured_limit ?? 0} used`,
    },
  ];
  return (
    <div className="mb-5 rounded-[18px] border border-sage/40 bg-sage-tint/20 p-5">
      <p className="text-[16px] font-semibold text-ink">
        {name}
        {store.plan_free ? " (free from TryOnU)" : ""} · active until {ends}
      </p>
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        {bars.map((b) => {
          const pct = b.total > 0 ? Math.min(100, Math.round((b.used / b.total) * 100)) : 0;
          return (
            <div key={b.label}>
              <p className="text-[14px] font-medium text-muted">{b.label}</p>
              <p className="mt-0.5 text-[18px] font-semibold text-ink">{b.text}</p>
              <span className="mt-1.5 block h-2 overflow-hidden rounded-full bg-paper-2">
                <span className={`block h-full rounded-full ${pct >= 90 ? "bg-[#c0503a]" : "bg-sage"}`} style={{ width: `${pct}%` }} />
              </span>
            </div>
          );
        })}
        <div>
          <p className="text-[14px] font-medium text-muted">🎁 Try-on credits</p>
          <p className="mt-0.5 text-[18px] font-semibold text-ink">{(store.tryon_credits ?? 0).toLocaleString()} left</p>
          <p className="mt-1 text-[13.5px] leading-snug text-muted">1 credit = 1 shopper trying on your product for free.</p>
        </div>
      </div>
      <p className="mt-4 text-[14px] leading-relaxed text-ink-soft">
        <b>How it works:</b> each free try-on of your product uses 1 credit. A failed try-on gives it back. A new plan
        <b> adds</b> its credits to what you have.
      </p>
    </div>
  );
}

/** Shown instead of a page that needs a plan, with the way to get one. */
function NeedsPlan({ go, what }: { go: (tab: Tab) => void; what: string }) {
  return (
    <section className="rounded-[24px] border border-line bg-surface px-6 py-12 text-center">
      <p className="text-[40px]" aria-hidden="true">🔒</p>
      <h2 className="mt-2 font-display text-[24px] text-ink">Unlock a plan to {what}</h2>
      <p className="mx-auto mt-2 max-w-md text-[15.5px] text-muted">
        Your plan sets how many products you can sell. Then add them here.
      </p>
      <button
        type="button"
        onClick={() => go("plan")}
        className="tu-press mt-5 inline-flex min-h-[44px] items-center rounded-full bg-sage px-6 text-[16px] font-semibold text-white hover:bg-sage-deep"
      >
        Choose a plan →
      </button>
      <p className="mt-3 text-[13.5px] text-faint">Already paid? Open Payments and press “Check payment again”.</p>
    </section>
  );
}

/** The few steps to go live, ticked off as they're done, each with its button. */
function NextSteps({ store, go }: { store: Store; go: (tab: Tab) => void }) {
  if (store.live && store.product_count > 0) return null;
  const steps: { done: boolean; title: string; text: string; action?: { label: string; tab: Tab } }[] = [
    { done: true, title: "Open your store", text: "Your store details are saved." },
    {
      done: store.status === "approved",
      title: "Approval by TryOnU",
      text: store.status === "approved" ? "Approved." : "We check every new store. You'll get an email.",
    },
    {
      done: store.plan_active,
      title: "Unlock a plan",
      text: store.plan_active ? "Your plan is active." : "Choose how many products you want to sell.",
      action: store.plan_active ? undefined : { label: "Choose a plan", tab: "plan" },
    },
    {
      done: store.product_count > 0,
      title: "Add your products",
      text: store.product_count > 0 ? `${store.product_count} added.` : "Add them one by one, or import a file.",
      action: store.product_count > 0 ? undefined : { label: "Add products", tab: "products" },
    },
  ];
  return (
    <section className="rounded-[24px] border border-line bg-surface p-6">
      <h2 className="font-display text-[20px] text-ink">Get your store live</h2>
      <ol className="mt-4 grid gap-3 sm:grid-cols-2">
        {steps.map((step, i) => (
          <li
            key={step.title}
            className={`flex items-start gap-3 rounded-[16px] border px-4 py-3.5 ${step.done ? "border-sage/40 bg-sage-tint/30" : "border-line"}`}
          >
            <span
              className={`grid h-8 w-8 shrink-0 place-items-center rounded-full text-[15px] font-semibold ${
                step.done ? "bg-sage text-white" : "border border-line-strong text-ink-soft"
              }`}
              aria-hidden="true"
            >
              {step.done ? "✓" : i + 1}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[16px] font-semibold text-ink">
                {step.title}
                <span className="sr-only">{step.done ? " (done)" : " (to do)"}</span>
              </p>
              <p className="mt-0.5 text-[14.5px] text-muted">{step.text}</p>
              {step.action && (
                <button
                  type="button"
                  onClick={() => go(step.action!.tab)}
                  className="tu-press mt-2.5 inline-flex min-h-[40px] items-center rounded-full bg-sage px-4 text-[14.5px] font-semibold text-white hover:bg-sage-deep"
                >
                  {step.action.label} →
                </button>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

const STATUS: Record<string, { label: string; tone: "good" | "bad" | "warn" | "neutral"; text: string }> = {
  pending: { label: "Waiting for approval", tone: "warn", text: "We're checking your store. You can add products now; they show once it's approved." },
  approved: { label: "Approved", tone: "good", text: "Your store is approved." },
  rejected: { label: "Not approved", tone: "bad", text: "Your store wasn't approved." },
  suspended: { label: "Suspended", tone: "bad", text: "Your store is suspended; its products are hidden from shoppers." },
};

function StoreHeader({ store }: { store: Store }) {
  const status = STATUS[store.status] ?? STATUS.pending;
  const expires = store.plan_expires_at ? new Date(store.plan_expires_at) : null;
  return (
    <div className="rounded-[24px] border border-line bg-surface p-6">
      <div className="flex flex-wrap items-center gap-4">
        {store.logo_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={store.logo_url} alt="" className="h-14 w-14 rounded-[14px] border border-line object-cover" />
        ) : (
          <div className="grid h-14 w-14 place-items-center rounded-[14px] bg-sage text-[22px] font-semibold text-white">
            {store.name.slice(0, 1).toUpperCase()}
          </div>
        )}
        <div className="min-w-0 flex-1">
          <h1 className="font-display text-[28px] leading-tight text-ink">{store.name}</h1>
          <p className="text-[14px] text-muted">{countryName(store.country)}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={status.tone}>{status.label}</Badge>
          <Badge tone={store.live ? "good" : "neutral"}>{store.live ? "Live: shoppers see your products" : "Not live yet"}</Badge>
        </div>
      </div>
      <p className="mt-2 text-[14px] text-muted">🚚 Delivers: {deliveryText(store.delivery, store.delivery_countries, store.country)}</p>
      <p className="mt-4 text-[14.5px] text-ink-soft">
        {status.text}
        {store.status_note ? ` ${store.status_note}` : ""}
        {store.live && (
          <a href={`/stores/${store.slug}`} target="_blank" rel="noopener" className="ml-2 font-medium text-sage-deep hover:underline">
            View your public store page ↗
          </a>
        )}
      </p>
      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat
          label="Plan"
          value={
            store.plan_active
              ? `${(store.plan_code ?? "").replace(/^./, (c) => c.toUpperCase())}${store.plan_free ? " (free)" : ""}`
              : "None"
          }
        />
        <Stat label="Plan ends" value={store.plan_active && expires ? expires.toLocaleDateString() : "Not unlocked yet"} />
        <Stat label="Products" value={`${store.product_count} of ${store.plan_active ? store.plan_product_limit : 0}`} />
        <Stat label="★ Featured" value={`${store.featured_count ?? 0} of ${store.plan_featured_limit ?? 0}`} />
        <Stat label="🎁 Try-on credits left" value={`${store.tryon_credits ?? 0}`} />
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-[16px] border border-line bg-paper-2/50 px-4 py-3">
      <p className="text-[12px] uppercase tracking-[0.1em] text-faint">{label}</p>
      <p className="mt-1 text-[16px] font-semibold text-ink">{value}</p>
    </div>
  );
}

function PlansSection({ store }: { store: Store }) {
  const qc = useQueryClient();
  const plans = useQuery({ queryKey: ["store-plans"], queryFn: storesApi.plans });
  const checkoutProvider = useCheckoutProvider();
  const buy = useMutation({
    mutationFn: (plan: StorePlan) => storesApi.buyPlan(plan.code),
    onSuccess: (res) => {
      if (res.checkout_url) window.location.assign(res.checkout_url);
      else qc.invalidateQueries({ queryKey: STORE_KEY });
    },
  });
  const subscribe = useMutation({
    mutationFn: (plan: StorePlan) => storesApi.subscribePlan(plan.code),
    onSuccess: (res) => window.location.assign(res.checkout_url),
  });
  const sync = useMutation({
    mutationFn: storesApi.syncSubscription,
    onSuccess: (res) => {
      qc.setQueryData(STORE_KEY, res.store);
      qc.invalidateQueries({ queryKey: ["business", "payments"] });
    },
  });
  const cancel = useMutation({ mutationFn: storesApi.cancelSubscription, onSuccess: (s) => qc.setQueryData(STORE_KEY, s) });

  // back from PayPal's subscription page: ask our server to confirm with PayPal
  const [returned, setReturned] = useState<string | null>(null);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const flag = params.get("subscription");
    if (!flag) return;
    setReturned(flag);
    window.history.replaceState(null, "", `${window.location.pathname}#plan`);
    if (flag === "done") sync.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const subscribed = !!store.subscription_status && !["CANCELLED", "SUSPENDED", "EXPIRED"].includes(store.subscription_status);
  const busy = buy.isPending || subscribe.isPending;
  return (
    <Section
      title={store.plan_active ? "Your plan" : "Unlock a plan"}
      hint="Pay for 30 days, or turn on auto-renew to pay every month until you stop it."
    >
      {store.plan_active && <PlanAllowance store={store} />}
      {returned === "cancelled" && (
        <p className="mb-3 rounded-[14px] border border-line bg-paper-2/60 px-4 py-2.5 text-[14px] text-ink-soft">
          You left PayPal before confirming auto-renew. Nothing was charged.
        </p>
      )}
      {subscribed && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-[16px] border border-sage/40 bg-sage-tint/40 px-4 py-3 text-[14.5px]">
          <span className="text-ink-soft">
            {store.auto_renew && store.plan_active
              ? `Auto-renew is on: PayPal renews your ${store.subscription_plan_code ?? ""} plan every period.`
              : sync.isPending
                ? "Checking with PayPal…"
                : "Auto-renew is waiting for PayPal to confirm the first payment. This can take a minute."}
          </span>
          <span className="flex gap-2">
            <SmallButton disabled={sync.isPending} onClick={() => sync.mutate()}>
              {sync.isPending ? "Checking…" : "Check now"}
            </SmallButton>
            <SmallButton tone="danger" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
              {cancel.isPending ? "Turning off…" : "Turn off auto-renew"}
            </SmallButton>
          </span>
        </div>
      )}
      {!subscribed && store.subscription_status === "CANCELLED" && store.plan_active && (
        <p className="mb-3 text-[14px] text-muted">Auto-renew is off. Your plan stays active until it ends.</p>
      )}
      {plans.data && (
        <div className="grid gap-4 sm:grid-cols-3">
          {plans.data.map((plan) => {
            const current = store.plan_active && store.plan_code === plan.code;
            return (
              <div
                key={plan.id}
                className={`flex flex-col rounded-[20px] border p-5 ${current ? "border-sage ring-2 ring-sage/30" : "border-line"}`}
              >
                <p className="font-display text-[20px] text-ink">{plan.name}</p>
                <p className="mt-1 text-[24px] font-semibold text-ink">
                  {formatPrice(plan.price_cents, plan.currency)}
                  <span className="text-[14px] font-normal text-muted"> / {plan.duration_days} days</span>
                </p>
                <p className="mt-2 text-[15px] text-ink-soft">Up to {plan.product_limit.toLocaleString()} products</p>
                {plan.tryon_credits > 0 && (
                  <p className="mt-1 text-[15px] text-ink-soft">
                    🎁 {plan.tryon_credits.toLocaleString()} free try-ons for your shoppers
                  </p>
                )}
                {plan.featured_limit > 0 && (
                  <p className="mt-1 text-[15px] text-ink-soft">
                    <span className="text-sage-deep">★</span> Feature {plan.featured_limit.toLocaleString()} products: shown first to shoppers
                  </p>
                )}
                <div className="mt-auto space-y-2 pt-5">
                  <Button
                    size="md"
                    variant={current ? "outline" : "primary"}
                    className="w-full"
                    disabled={busy}
                    onClick={() => buy.mutate(plan)}
                  >
                    {buy.isPending && buy.variables?.id === plan.id
                      ? "Opening checkout…"
                      : current
                        ? `Renew ${plan.duration_days} days`
                        : store.plan_active
                          ? `Switch to ${plan.name}`
                          : `Unlock ${plan.duration_days} days`}
                  </Button>
                  {/* auto-renew is a PayPal subscription: offered only while PayPal takes the payments */}
                  {!subscribed && checkoutProvider === "paypal" && (
                    <Button size="md" variant="outline" className="w-full" disabled={busy} onClick={() => subscribe.mutate(plan)}>
                      {subscribe.isPending && subscribe.variables?.id === plan.id ? "Opening PayPal…" : "Auto-renew"}
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
      {(buy.isError || subscribe.isError || sync.isError || cancel.isError) && (
        <div className="mt-3"><ErrorNote>{errorText(buy.error ?? subscribe.error ?? sync.error ?? cancel.error)}</ErrorNote></div>
      )}
    </Section>
  );
}

// -------------------------------------------------------------------- products

const EMPTY: StoreProductInput = { name: "", price_cents: 0, currency: "usd", product_url: "", gender: "women", category: "", color: "", description: "" };

function ProductsSection({ store }: { store: Store }) {
  const qc = useQueryClient();
  const products = useQuery({ queryKey: ["business", "products"], queryFn: storesApi.products });
  const [editing, setEditing] = useState<StoreProduct | null>(null);
  const [adding, setAdding] = useState(false);
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["business", "products"] });
    qc.invalidateQueries({ queryKey: STORE_KEY });
  };
  const toggle = useMutation({
    mutationFn: (p: StoreProduct) => storesApi.editProduct(p.id, { is_active: !p.is_active }),
    onSuccess: refresh,
  });
  const remove = useMutation({ mutationFn: (p: StoreProduct) => storesApi.deleteProduct(p.id), onSuccess: refresh });
  const fileRef = useRef<HTMLInputElement>(null);
  const upload = useMutation({ mutationFn: (file: File) => storesApi.importFile(file), onSuccess: refresh });
  const full = store.product_count >= store.plan_product_limit;
  const featureFull = (store.featured_count ?? 0) >= (store.plan_featured_limit ?? 0);
  const feature = useMutation({
    mutationFn: (p: StoreProduct) => storesApi.editProduct(p.id, { is_featured: !p.is_featured }),
    onSuccess: refresh,
  });

  return (
    <Section
      title="Products"
      hint={
        store.plan_active
          ? `${store.product_count} of ${store.plan_product_limit} on sale · ★ ${store.featured_count ?? 0} of ${store.plan_featured_limit ?? 0} featured. Featured products are shown first when they match what a shopper asks for, and first of all to shoppers in your country. Products without a photo aren't shown.`
          : "Unlock a plan to add products."
      }
      action={
        store.plan_active && !adding && !editing ? (
          <div className="flex flex-wrap gap-2">
            <SmallButton disabled={full || upload.isPending} onClick={() => fileRef.current?.click()}>
              {upload.isPending ? "Uploading…" : "Upload CSV/JSON file"}
            </SmallButton>
            <SmallButton tone="primary" disabled={full} onClick={() => setAdding(true)}>
              {full ? "Plan limit reached" : "+ Add product"}
            </SmallButton>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.json,.tsv,.txt,text/csv,application/json"
              hidden
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) upload.mutate(file);
                e.target.value = "";
              }}
            />
          </div>
        ) : null
      }
    >
      {(adding || editing) && (
        <ProductForm
          key={editing?.id ?? "new"}
          store={store}
          initial={editing}
          onDone={() => {
            setAdding(false);
            setEditing(null);
            refresh();
          }}
          onCancel={() => {
            setAdding(false);
            setEditing(null);
          }}
        />
      )}
      {(toggle.isError || remove.isError || upload.isError || feature.isError) && (
        <ErrorNote>{errorText(toggle.error ?? remove.error ?? upload.error ?? feature.error)}</ErrorNote>
      )}
      {upload.data && <p className="mb-3 text-[14px] text-ink-soft">{upload.data.result}</p>}
      {products.data && products.data.length === 0 && !adding && (
        <p className="rounded-[16px] border border-dashed border-line p-6 text-center text-[15px] text-muted">
          No products yet{store.plan_active ? ". Add one, or connect your feed below." : "."}
        </p>
      )}
      {products.data && products.data.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {products.data.map((p) => (
            <article key={p.id} className={`flex flex-col overflow-hidden rounded-[18px] border bg-surface ${p.is_active ? "border-line" : "border-dashed border-line opacity-60"}`}>
              <div className="relative aspect-[4/5] bg-white">
                {p.images[0] ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={p.images[0]} alt={p.name} className="h-full w-full object-contain p-2" />
                ) : (
                  <div className="grid h-full place-items-center text-[13px] text-faint">No photo yet</div>
                )}
                <span className="absolute left-2 top-2 rounded-full bg-black/70 px-2 py-0.5 text-[11px] font-semibold text-white">
                  {p.source === "feed" ? "From feed" : "Added by you"}
                </span>
                {p.is_featured && (
                  <span className="absolute right-2 top-2 rounded-full bg-sage px-2 py-0.5 text-[11.5px] font-semibold text-white">★ Featured</span>
                )}
              </div>
              <div className="flex flex-1 flex-col p-3">
                <p className="line-clamp-2 text-[13.5px] leading-snug text-ink">{p.name}</p>
                <p className="mt-1 text-[15px] font-semibold text-ink">{formatPrice(p.price_cents, p.currency)}</p>
                {p.delivery && (
                  <p className="mt-1 text-[12.5px] text-muted">
                    🚚 {p.delivery === "worldwide" ? "Worldwide" : `Only in ${countryName(store.country)}`}
                  </p>
                )}
                <div className="mt-auto flex flex-wrap gap-1.5 pt-3">
                  <SmallButton
                    tone={p.is_featured ? "primary" : "neutral"}
                    disabled={feature.isPending || !p.is_active || (!p.is_featured && featureFull)}
                    onClick={() => feature.mutate(p)}
                  >
                    {p.is_featured ? "★ Featured" : "☆ Feature"}
                  </SmallButton>
                  <SmallButton onClick={() => setEditing(p)}>Edit</SmallButton>
                  <SmallButton disabled={toggle.isPending} onClick={() => toggle.mutate(p)}>
                    {p.is_active ? "Hide" : "Show"}
                  </SmallButton>
                  <SmallButton tone="danger" disabled={remove.isPending} onClick={() => remove.mutate(p)}>
                    Delete
                  </SmallButton>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </Section>
  );
}

function ProductForm({
  store,
  initial,
  onDone,
  onCancel,
}: {
  store: Store;
  initial: StoreProduct | null;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<StoreProductInput>(
    initial
      ? { ...initial, category: initial.category ?? "", color: initial.color ?? "", description: initial.description ?? "" }
      : EMPTY,
  );
  const [price, setPrice] = useState(initial ? (initial.price_cents / 100).toFixed(2) : "");
  const [product, setProduct] = useState<StoreProduct | null>(initial);
  const fileRef = useRef<HTMLInputElement>(null);
  const set = (patch: Partial<StoreProductInput>) => setForm((f) => ({ ...f, ...patch }));
  const priceCents = Math.round(Number(price) * 100);
  const valid = form.name.trim().length >= 2 && priceCents > 0 && /^https?:\/\//.test(form.product_url.trim());

  const save = useMutation({
    mutationFn: () => {
      const body = {
        ...form,
        name: form.name.trim(),
        product_url: form.product_url.trim(),
        price_cents: priceCents,
        category: form.category?.trim() || null,
        color: form.color?.trim() || null,
        description: form.description?.trim() || null,
        delivery: form.delivery ?? null,
      };
      return product ? storesApi.editProduct(product.id, body) : storesApi.addProduct(body);
    },
    onSuccess: (saved) => setProduct(saved),
  });
  const upload = useMutation({
    mutationFn: async (files: FileList) => {
      let latest = product!;
      for (const file of Array.from(files)) latest = await storesApi.addImage(latest.id, file);
      return latest;
    },
    onSuccess: setProduct,
  });
  const dropImage = useMutation({ mutationFn: (index: number) => storesApi.removeImage(product!.id, index), onSuccess: setProduct });

  return (
    <form
      className="mb-5 space-y-3 rounded-[20px] border border-line bg-surface p-5"
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        if (valid) save.mutate();
      }}
    >
      <p className="text-[15px] font-semibold text-ink">{initial ? `Edit “${initial.name}”` : product ? "Product saved: add its photos" : "New product"}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Name">
          <input value={form.name} onChange={(e) => set({ name: e.target.value })} maxLength={512} className={`${inputClass} w-full`} />
        </Field>
        <Field label="Link to this product in your store">
          <input value={form.product_url} onChange={(e) => set({ product_url: e.target.value })} placeholder="https://" className={`${inputClass} w-full`} />
        </Field>
        <Field label="Price">
          <div className="flex gap-2">
            <input type="number" min={0.01} step={0.01} value={price} onChange={(e) => setPrice(e.target.value)} className={`${inputClass} w-full`} />
            <select value={form.currency} onChange={(e) => set({ currency: e.target.value })} className={`${inputClass} w-24`}>
              {["usd", "eur", "gbp", "pkr", "inr", "aed", "sar", "cad", "aud"].map((c) => (
                <option key={c} value={c}>{c.toUpperCase()}</option>
              ))}
            </select>
          </div>
        </Field>
        <Field label="For">
          <select value={form.gender} onChange={(e) => set({ gender: e.target.value })} className={`${inputClass} w-full`}>
            {[["women", "Women"], ["men", "Men"], ["unisex", "Everyone"], ["girls", "Girls"], ["boys", "Boys"]].map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </Field>
        <Field label="Category" hint="e.g. Lehenga, Kurta, Earrings, Khussa">
          <input value={form.category ?? ""} onChange={(e) => set({ category: e.target.value })} maxLength={120} className={`${inputClass} w-full`} />
        </Field>
        <Field label="Colour">
          <input value={form.color ?? ""} onChange={(e) => set({ color: e.target.value })} maxLength={60} className={`${inputClass} w-full`} />
        </Field>
        <Field label="Delivery for this product" hint="Shoppers only see it where it can be delivered.">
          <select
            value={form.delivery ?? ""}
            onChange={(e) => set({ delivery: (e.target.value || null) as StoreProductInput["delivery"] })}
            className={`${inputClass} w-full`}
          >
            <option value="">Same as my store ({deliveryText(store.delivery, store.delivery_countries, store.country)})</option>
            <option value="domestic">Only in {countryName(store.country)}</option>
            <option value="worldwide">Worldwide</option>
          </select>
        </Field>
      </div>
      <Field label="Description">
        <textarea value={form.description ?? ""} onChange={(e) => set({ description: e.target.value })} rows={3} maxLength={4000} className={`${inputClass} h-auto w-full py-2`} />
      </Field>
      {save.isError && <ErrorNote>{errorText(save.error)}</ErrorNote>}
      <div className="flex flex-wrap gap-2">
        <SmallButton type="submit" tone="primary" disabled={!valid || save.isPending}>
          {save.isPending ? "Saving…" : product ? "Save changes" : "Save and add photos"}
        </SmallButton>
        <SmallButton onClick={product ? onDone : onCancel}>{product ? "Done" : "Cancel"}</SmallButton>
      </div>

      {product && (
        <div className="border-t border-line pt-4">
          <p className="text-[14px] font-semibold text-ink">Photos <span className="font-normal text-muted">(up to 6; the first is the main photo)</span></p>
          <div className="mt-3 flex flex-wrap gap-3">
            {product.images.map((src, i) => (
              <div key={src} className="relative h-28 w-24 overflow-hidden rounded-[12px] border border-line bg-white">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={src} alt="" className="h-full w-full object-contain p-1" />
                <button
                  type="button"
                  aria-label="Remove photo"
                  onClick={() => dropImage.mutate(i)}
                  className="absolute right-1 top-1 grid h-6 w-6 place-items-center rounded-full bg-black/70 text-[14px] text-white"
                >
                  ×
                </button>
              </div>
            ))}
            {product.images.length < 6 && (
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                disabled={upload.isPending}
                className="grid h-28 w-24 place-items-center rounded-[12px] border border-dashed border-line-strong text-[13px] text-muted hover:text-ink"
              >
                {upload.isPending ? "Uploading…" : "+ Add photo"}
              </button>
            )}
          </div>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            multiple
            hidden
            onChange={(e) => {
              if (e.target.files?.length) upload.mutate(e.target.files);
              e.target.value = "";
            }}
          />
          {(upload.isError || dropImage.isError) && <div className="mt-2"><ErrorNote>{errorText(upload.error ?? dropImage.error)}</ErrorNote></div>}
        </div>
      )}
    </form>
  );
}

// ------------------------------------------------------------------------ feed

function FeedSection({ store }: { store: Store }) {
  const qc = useQueryClient();
  const [url, setUrl] = useState(store.feed_url ?? "");
  const save = useMutation({
    mutationFn: () => storesApi.setFeed(url.trim() || null),
    onSuccess: (s) => qc.setQueryData(STORE_KEY, s),
  });
  const run = useMutation({
    mutationFn: storesApi.importFeed,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: STORE_KEY });
      qc.invalidateQueries({ queryKey: ["business", "products"] });
    },
  });
  return (
    <Section
      title="Add products from a link"
      hint="Paste your product list link (CSV or JSON, e.g. from Shopify or WooCommerce). We update it every night."
    >
      <div className="flex flex-wrap gap-2">
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://yourstore.com/products.csv"
          className={`${inputClass} min-w-[260px] flex-1`}
        />
        <SmallButton tone="primary" disabled={save.isPending || url.trim() === (store.feed_url ?? "")} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : "Save link"}
        </SmallButton>
        <SmallButton disabled={!store.feed_url || !store.plan_active || run.isPending} onClick={() => run.mutate()}>
          {run.isPending ? "Importing…" : "Import now"}
        </SmallButton>
      </div>
      {(save.isError || run.isError) && <div className="mt-2"><ErrorNote>{errorText(save.error ?? run.error)}</ErrorNote></div>}
      {(run.data?.result || store.feed_last_result) && (
        <p className="mt-3 text-[14px] text-ink-soft">
          {run.data?.result ?? store.feed_last_result}
          {store.feed_last_run_at && !run.data ? ` (${new Date(store.feed_last_run_at).toLocaleString()})` : ""}
        </p>
      )}
      <details className="mt-3 text-[13.5px] text-muted">
        <summary className="cursor-pointer">Which columns does the feed need?</summary>
        <p className="mt-2">
          Each product needs a <b>name</b>, <b>price</b>, <b>link</b> and an <b>image</b> link. Anything else (colour, category,
          description…) is optional.
        </p>
      </details>
    </Section>
  );
}

// --------------------------------------------------------------------- profile

function ProfileSection({ store }: { store: Store }) {
  const qc = useQueryClient();
  const [name, setName] = useState(store.name);
  const [country, setCountry] = useState(store.country);
  const [website, setWebsite] = useState(store.website_url ?? "");
  const [email, setEmail] = useState(store.contact_email ?? "");
  const [whatsapp, setWhatsapp] = useState(store.whatsapp ?? "");
  const [description, setDescription] = useState(store.description ?? "");
  const logoRef = useRef<HTMLInputElement>(null);
  const save = useMutation({
    mutationFn: () =>
      storesApi.update({
        name: name.trim(),
        country,
        website_url: website.trim() || null,
        contact_email: email.trim() || null,
        whatsapp: whatsapp.trim() || null,
        description: description.trim() || null,
      }),
    onSuccess: (s) => qc.setQueryData(STORE_KEY, s),
  });
  const logo = useMutation({ mutationFn: (file: File) => storesApi.uploadLogo(file), onSuccess: (s) => qc.setQueryData(STORE_KEY, s) });

  return (
    <div className="space-y-6">
    <DeliverySection store={store} />
    <Section title="Store details">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Store name">
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} className={`${inputClass} w-full`} />
        </Field>
        <Field label="Country">
          <CountrySelect value={country} onChange={setCountry} />
        </Field>
        <Field label="Website">
          <input value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="https://" className={`${inputClass} w-full`} />
        </Field>
        <Field label="Contact email">
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={`${inputClass} w-full`} />
        </Field>
        <Field label="WhatsApp number (shoppers order here)">
          <input
            type="tel"
            inputMode="tel"
            value={whatsapp}
            onChange={(e) => setWhatsapp(e.target.value)}
            placeholder="+92 300 1234567"
            className={`${inputClass} w-full`}
          />
        </Field>
      </div>
      <div className="mt-3">
        <Field label="About your store">
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} maxLength={2000} className={`${inputClass} h-auto w-full py-2`} />
        </Field>
      </div>
      {(save.isError || logo.isError) && <div className="mt-2"><ErrorNote>{errorText(save.error ?? logo.error)}</ErrorNote></div>}
      <div className="mt-3 flex flex-wrap gap-2">
        <SmallButton tone="primary" disabled={save.isPending || name.trim().length < 2} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : save.isSuccess ? "Saved" : "Save details"}
        </SmallButton>
        <SmallButton disabled={logo.isPending} onClick={() => logoRef.current?.click()}>
          {logo.isPending ? "Uploading…" : store.logo_url ? "Change logo" : "Upload logo"}
        </SmallButton>
        <input
          ref={logoRef}
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) logo.mutate(file);
            e.target.value = "";
          }}
        />
      </div>
    </Section>
    </div>
  );
}

const DELIVERY_CHOICES: { value: StoreDelivery; title: string; text: string }[] = [
  { value: "domestic", title: "Only in my country", text: "Shoppers in other countries won't see your products." },
  { value: "countries", title: "My country and some others", text: "Choose the countries you deliver to." },
  { value: "worldwide", title: "Worldwide", text: "Every shopper can see and buy your products." },
];

/** Only my country / my country and some others / worldwide, as three big choices. */
function DeliveryChooser({
  home,
  mode,
  onMode,
  countries,
  onCountries,
}: {
  home: string;
  mode: StoreDelivery;
  onMode: (m: StoreDelivery) => void;
  countries: string[];
  onCountries: (c: string[]) => void;
}) {
  const [adding, setAdding] = useState("");
  return (
    <>
      <div role="radiogroup" aria-label="Delivery" className="grid gap-3 md:grid-cols-3">
        {DELIVERY_CHOICES.map((c) => (
          <button
            key={c.value}
            type="button"
            role="radio"
            aria-checked={mode === c.value}
            onClick={() => onMode(c.value)}
            className={`rounded-[16px] border p-4 text-left transition-colors ${
              mode === c.value ? "border-sage bg-sage-tint/40 ring-2 ring-sage/30" : "border-line hover:border-line-strong"
            }`}
          >
            <p className="text-[16px] font-semibold text-ink">
              {mode === c.value ? "● " : "○ "}
              {c.value === "domestic" ? `Only in ${countryName(home)}` : c.title}
            </p>
            <p className="mt-1 text-[14px] text-muted">{c.text}</p>
          </button>
        ))}
      </div>
      {mode === "countries" && (
        <div className="mt-4 rounded-[16px] border border-line p-4">
          <p className="text-[14.5px] text-ink-soft">
            {countryName(home)} is always included. Also delivering to:
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {countries.length === 0 && <span className="text-[14px] text-muted">No countries added yet.</span>}
            {countries.map((c) => (
              <span key={c} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-paper-2 px-3 py-1 text-[14px] text-ink">
                {countryName(c)}
                <button
                  type="button"
                  aria-label={`Remove ${countryName(c)}`}
                  onClick={() => onCountries(countries.filter((x) => x !== c))}
                  className="text-muted hover:text-[#a4553f]"
                >
                  ✕
                </button>
              </span>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <div className="w-64">
              <CountrySelect value={adding} onChange={setAdding} />
            </div>
            <SmallButton
              disabled={!adding || adding === home || countries.includes(adding)}
              onClick={() => {
                onCountries([...countries, adding].sort());
                setAdding("");
              }}
            >
              + Add country
            </SmallButton>
          </div>
        </div>
      )}
    </>
  );
}

/** Where the store delivers: shoppers only see products that can reach them. */
function DeliverySection({ store }: { store: Store }) {
  const qc = useQueryClient();
  const [mode, setMode] = useState<StoreDelivery>(store.delivery ?? "domestic");
  const [countries, setCountries] = useState<string[]>(store.delivery_countries ?? []);
  const save = useMutation({
    mutationFn: () => storesApi.update({ delivery: mode, delivery_countries: mode === "countries" ? countries : [] }),
    onSuccess: (s) => qc.setQueryData(STORE_KEY, s),
  });
  const changed =
    mode !== (store.delivery ?? "domestic") ||
    (mode === "countries" && countries.join() !== (store.delivery_countries ?? []).join());
  return (
    <Section
      title="Where do you deliver?"
      hint={`Shoppers see only what you can deliver to them. Now: ${deliveryText(store.delivery, store.delivery_countries, store.country)}.`}
    >
      <DeliveryChooser home={store.country} mode={mode} onMode={setMode} countries={countries} onCountries={setCountries} />
      {save.isError && <div className="mt-3"><ErrorNote>{errorText(save.error)}</ErrorNote></div>}
      <div className="mt-4 flex items-center gap-3">
        <SmallButton
          tone="primary"
          disabled={save.isPending || !changed || (mode === "countries" && countries.length === 0)}
          onClick={() => save.mutate()}
        >
          {save.isPending ? "Saving…" : "Save delivery"}
        </SmallButton>
        {save.isSuccess && !changed && <span className="text-[14px] font-medium text-sage-deep">✓ Saved</span>}
      </div>
    </Section>
  );
}

// ----------------------------------------------------------- stats & payments

function StatsSection() {
  const stats = useQuery({ queryKey: ["business", "stats"], queryFn: storesApi.stats });
  if (!stats.data) return null;
  const s = stats.data;
  return (
    <Section
      title="Performance"
      hint={`The last ${s.days} days: how many shoppers saw, clicked, tried on, saved and liked your products.`}
    >
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Views" value={s.views.toLocaleString()} />
        <Stat label="Shop clicks" value={s.clicks.toLocaleString()} />
        <Stat label="Click rate" value={s.views ? `${((s.clicks / s.views) * 100).toFixed(1)}%` : "—"} />
        <Stat label="Try-ons" value={s.tryons.toLocaleString()} />
        <Stat label="Saved in looks" value={(s.saves ?? 0).toLocaleString()} />
        <Stat label="Community likes" value={(s.likes ?? 0).toLocaleString()} />
        <Stat label="Price alerts" value={(s.alerts ?? 0).toLocaleString()} />
        <Stat label="Try-on rate" value={s.views ? `${((s.tryons / s.views) * 100).toFixed(1)}%` : "—"} />
      </div>
      {s.top.length > 0 ? (
        <div className="mt-4 divide-y divide-line rounded-[16px] border border-line">
          {s.top.map((row) => (
            <div key={row.store_product_id} className="flex items-center justify-between gap-3 px-4 py-2.5 text-[14px]">
              <span className="min-w-0 flex-1 truncate text-ink-soft">{row.name}</span>
              <span className="shrink-0 text-right text-muted">
                {row.views} views · {row.clicks} clicks · {row.tryons} try-ons
                {row.saves ? ` · ${row.saves} saved` : ""}
                {row.likes ? ` · ${row.likes} likes` : ""}
                {row.alerts ? ` · ${row.alerts} waiting for a lower price` : ""}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-[14px] text-muted">No views yet. They appear here once shoppers find your products.</p>
      )}
    </Section>
  );
}

function PaymentsSection({ go }: { go: (tab: Tab) => void }) {
  const qc = useQueryClient();
  const payments = useQuery({ queryKey: ["business", "payments"], queryFn: storesApi.payments });
  // a payment left "not completed" (PayPal closed early, or the return page
  // didn't load): ask PayPal again; the plan unlocks only if the money was taken
  const check = useMutation({
    mutationFn: (paymentId: string) => creditsApi.capturePurchase(paymentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["business", "payments"] });
      qc.invalidateQueries({ queryKey: STORE_KEY });
    },
  });
  return (
    <Section title="Payments" hint="Every plan payment. A plan unlocks only when its payment says Paid.">
      {payments.isLoading ? (
        <p className="text-[14px] text-muted">Loading…</p>
      ) : !payments.data || payments.data.length === 0 ? (
        <p className="rounded-[16px] border border-dashed border-line p-6 text-center text-[15px] text-muted">No payments yet.</p>
      ) : (
        <div className="divide-y divide-line rounded-[16px] border border-line">
          {payments.data.map((p) => {
            const pending = p.status !== "succeeded" && p.status !== "failed" && p.status !== "refunded";
            const checking = check.isPending && check.variables === p.id;
            const result = check.variables === p.id ? check.data?.status : undefined;
            return (
              <div key={p.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-[14.5px]">
                <span className="text-ink-soft">
                  {p.plan_name ?? "Plan"} plan · {new Date(p.created_at).toLocaleDateString()}
                  {pending && (
                    <span className="block text-[13.5px] text-muted">
                      {result === "pending"
                        ? "This payment wasn't received. No money was taken. Buy the plan again to finish."
                        : "Not finished, so no money was taken and the plan isn't unlocked."}
                    </span>
                  )}
                </span>
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold text-ink">{formatPrice(p.amount_cents, p.currency)}</span>
                  <Badge tone={p.status === "succeeded" ? "good" : p.status === "failed" ? "bad" : "neutral"}>
                    {p.status === "succeeded" ? "Paid" : p.status === "failed" ? "Failed" : p.status === "refunded" ? "Refunded" : "Not finished"}
                  </Badge>
                  {pending && (
                    <SmallButton disabled={check.isPending} onClick={() => check.mutate(p.id)}>
                      {checking ? "Checking…" : "Check payment again"}
                    </SmallButton>
                  )}
                </span>
              </div>
            );
          })}
        </div>
      )}
      {check.isError && <div className="mt-3"><ErrorNote>{errorText(check.error)}</ErrorNote></div>}
      {check.data?.status === "succeeded" && (
        <p className="mt-3 text-[14.5px] font-medium text-sage-deep">✓ Payment confirmed. Your plan is unlocked.</p>
      )}
      <div className="mt-4">
        <SmallButton tone="primary" onClick={() => go("plan")}>Go to plans</SmallButton>
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------- pieces

function Section({ title, hint, action, children }: { title: string; hint?: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-[24px] border border-line bg-surface p-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-2xl">
          <h2 className="font-display text-[20px] text-ink">{title}</h2>
          {hint && <p className="mt-1 text-[14px] leading-relaxed text-muted">{hint}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="text-[13.5px] font-medium text-ink-soft">{label}</span>
      <div className="mt-1">{children}</div>
      {hint && <span className="mt-1 block text-[12.5px] text-faint">{hint}</span>}
    </label>
  );
}

/** A country, picked by typing its name: the same picker as sign-up. */
export function CountrySelect({ value, onChange }: { value: string; onChange: (code: string) => void }) {
  return <CountryPicker value={value} onChange={onChange} placeholder="Choose a country" />;
}
