import { apiFetch } from "./client";
import type {
  AdminAIUsage,
  AdminAffiliateClick,
  AdminAuditEntry,
  AdminCreditPackage,
  AdminOverview,
  AdminProduct,
  AdminRetailer,
  AdminSettings,
  AdminStore,
  AdminStoreDetail,
  AdminStoreSummary,
  AdminSystemStatus,
  AdminTryOnJob,
  AdminUser,
  AdminUserDetail,
  AnalyticsReport,
  AuthResponse,
  CompatibilityPreview,
  ConnectionTestResult,
  CreditBalance,
  CreditPackage,
  CreditTransaction,
  DistractorOption,
  FittingProfileStatus,
  ForYouFeed,
  LiveProduct,
  Outfit,
  OutfitItemInput,
  Page,
  Product,
  ProductSearchParams,
  PublicStore,
  SavedLook,
  Store,
  StorePayment,
  StorePlan,
  StoreProduct,
  StoreProductInput,
  StoreStats,
  StylistAskInput,
  StylistResponse,
  SubscribeResponse,
  Subscription,
  SubscriptionPlanId,
  SubscriptionPlanOut,
  TaxonomyNode,
  TryOnJob,
  User,
  UserPhoto,
  UserPreference,
  WardrobeItem,
  WardrobeItemInput,
  StoreTryOns,
  StoreCosts,
  TryOnSponsor,
  DeveloperAccount,
  DeveloperApiKey,
  DeveloperApiKeyCreated,
  DeveloperCreditPack,
  DeveloperUsage,
  DeveloperPayment,
  AdminDeveloper,
} from "./types";

/* ---------------------------------- auth --------------------------------- */

export const auth = {
  register: (input: { email: string; password: string; full_name?: string; country?: string }) =>
    apiFetch<AuthResponse>("/api/v1/auth/register", { method: "POST", body: input }),

  login: (input: { email: string; password: string }) =>
    apiFetch<AuthResponse>("/api/v1/auth/login", { method: "POST", body: input }),

  logout: () => apiFetch<{ detail: string }>("/api/v1/auth/logout", { method: "POST" }),

  me: () => apiFetch<User>("/api/v1/auth/me"),

  /** the visitor's likely country, to pre-fill a country picker */
  countryHint: () => apiFetch<{ country: string | null }>("/api/v1/auth/country-hint"),

  googleLoginUrl: (apiBase: string) => `${apiBase}/api/v1/auth/google/login`,

  /** whether "Continue with Google" is set up on the server */
  googleEnabled: () => apiFetch<{ enabled: boolean }>("/api/v1/auth/google/enabled"),

  forgotPassword: (input: { email: string }) =>
    apiFetch<{ detail: string }>("/api/v1/auth/forgot-password", { method: "POST", body: input }),

  resetPassword: (input: { token: string; new_password: string }) =>
    apiFetch<{ detail: string }>("/api/v1/auth/reset-password", { method: "POST", body: input }),

  verifyEmail: (input: { token: string }) =>
    apiFetch<{ detail: string }>("/api/v1/auth/verify-email", { method: "POST", body: input }),

  resendVerification: () =>
    apiFetch<{ detail: string }>("/api/v1/auth/resend-verification", { method: "POST" }),

  changePassword: (input: { current_password: string | null; new_password: string }) =>
    apiFetch<AuthResponse>("/api/v1/auth/change-password", { method: "POST", body: input }),

  updateProfile: (input: { full_name: string }) =>
    apiFetch<User>("/api/v1/users/me", { method: "PATCH", body: input }),
};

/* --------------------------------- photos --------------------------------- */

export const photos = {
  list: () => apiFetch<UserPhoto[]>("/api/v1/photos"),

  status: () => apiFetch<FittingProfileStatus>("/api/v1/photos/status"),

  upload: (file: File, kind: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("kind", kind);
    return apiFetch<UserPhoto>("/api/v1/photos", { method: "POST", body: form, isFormData: true });
  },

  remove: (photoId: string) =>
    apiFetch<{ detail: string }>(`/api/v1/photos/${photoId}`, { method: "DELETE" }),
};

/* -------------------------------- products -------------------------------- */

function qs(params: Record<string, unknown>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

export const products = {
  list: (params: ProductSearchParams = {}, opts: { cache?: RequestCache } = {}) =>
    apiFetch<Page<Product>>(`/api/v1/products${qs(params)}`, { cache: opts.cache }),

  get: (productId: string) => apiFetch<Product>(`/api/v1/products/${productId}`),

  retailers: () => apiFetch<{ id: string; slug: string; name: string; logo_url: string | null }[]>(
    "/api/v1/products/meta/retailers",
  ),

  // Turns one live search result into a real, saved product — the only
  // point a live-searched item enters our database. Called right before
  // creating a try-on/outfit with it, not when it's merely shown on screen.
  selectLive: (input: { query: string; retailer_slug: string; retailer_product_id: string }) =>
    apiFetch<Product>("/api/v1/products/select-live", { method: "POST", body: input }),
};

/* ------------------------------ live search ------------------------------- */

export const liveSearch = {
  // Fetched fresh from retailer APIs on every call — never reads from or
  // writes to our product catalog. See products.selectLive to persist one.
  search: (q: string, limit = 24) =>
    apiFetch<LiveProduct[]>(`/api/v1/search/live?q=${encodeURIComponent(q)}&limit=${limit}`),
};

/* --------------------------------- credits --------------------------------- */

export const credits = {
  balance: () => apiFetch<CreditBalance>("/api/v1/credits/balance"),
  history: () => apiFetch<CreditTransaction[]>("/api/v1/credits/history"),
  packages: () => apiFetch<CreditPackage[]>("/api/v1/credits/packages"),
  // credits per try-on right now (admin-editable)
  pricing: () => apiFetch<{ tryon_cost: number; outfit_tryon_cost: number }>("/api/v1/credits/pricing"),
  purchase: (input: { credit_package_id: string }) =>
    apiFetch<{
      payment_id: string;
      status: string;
      client_secret: string | null;
      checkout_url: string | null;
      credits_granted: number | null;
      new_balance: number | null;
    }>("/api/v1/credits/purchase", { method: "POST", body: input }),
  // back from PayPal: the API confirms the payment with PayPal and grants the credits once
  capturePurchase: (paymentId: string) =>
    apiFetch<{
      payment_id: string;
      status: string;
      credits_granted: number | null;
      new_balance: number | null;
      plan_name?: string | null;
      plan_expires_at?: string | null;
      developer_tryons?: number | null;
    }>(`/api/v1/credits/purchase/${paymentId}/capture`, { method: "POST" }),
  purchaseStatus: (paymentId: string) =>
    apiFetch<{ payment_id: string; status: string; new_balance: number | null }>(
      `/api/v1/credits/purchase/${paymentId}`,
    ),
};

/* ---------------------------------- admin ----------------------------------- */

export const admin = {
  overview: () => apiFetch<AdminOverview>("/api/v1/admin/overview"),
  system: () => apiFetch<AdminSystemStatus>("/api/v1/admin/system"),
  analytics: (days: number) => apiFetch<AnalyticsReport>(`/api/v1/admin/analytics?days=${days}`),

  settings: () => apiFetch<AdminSettings>("/api/v1/admin/settings"),
  // null reverts that key to the server's .env / default
  updateSettings: (values: Record<string, string | null>) =>
    apiFetch<AdminSettings>("/api/v1/admin/settings", { method: "PUT", body: { values } }),
  testConnection: (group: string) =>
    apiFetch<ConnectionTestResult>(`/api/v1/admin/settings/test/${group}`, { method: "POST" }),

  users: (params: { q?: string; limit?: number; offset?: number } = {}) =>
    apiFetch<Page<AdminUser>>(`/api/v1/admin/users${qs(params)}`),
  userDetail: (userId: string) => apiFetch<AdminUserDetail>(`/api/v1/admin/users/${userId}`),
  updateUser: (userId: string, input: { is_active?: boolean; is_admin?: boolean; email_verified?: boolean }) =>
    apiFetch<AdminUser>(`/api/v1/admin/users/${userId}`, { method: "PATCH", body: input }),
  adjustCredits: (userId: string, input: { amount: number; note: string }) =>
    apiFetch<AdminUser>(`/api/v1/admin/users/${userId}/credits`, { method: "POST", body: input }),

  tryonJobs: (params: { status_filter?: string; limit?: number; offset?: number } = {}) =>
    apiFetch<Page<AdminTryOnJob>>(`/api/v1/admin/tryon-jobs${qs(params)}`),
  cancelTryonJob: (jobId: string) =>
    apiFetch<AdminTryOnJob>(`/api/v1/admin/tryon-jobs/${jobId}/cancel`, { method: "POST" }),

  products: (params: { q?: string; retailer?: string; active?: boolean; limit?: number; offset?: number } = {}) =>
    apiFetch<Page<AdminProduct>>(`/api/v1/admin/products${qs(params)}`),
  updateProduct: (productId: string, input: { is_active: boolean }) =>
    apiFetch<AdminProduct>(`/api/v1/admin/products/${productId}`, { method: "PATCH", body: input }),

  retailers: () => apiFetch<AdminRetailer[]>("/api/v1/admin/retailers"),
  updateRetailer: (slug: string, input: { is_active?: boolean; base_commission_pct?: number | null }) =>
    apiFetch<AdminRetailer[]>(`/api/v1/admin/retailers/${slug}`, { method: "PATCH", body: input }),

  creditPackages: () => apiFetch<AdminCreditPackage[]>("/api/v1/admin/credit-packages"),
  createCreditPackage: (input: { name: string; credits: number; price_cents: number; currency?: string }) =>
    apiFetch<AdminCreditPackage>("/api/v1/admin/credit-packages", { method: "POST", body: input }),
  updateCreditPackage: (
    packageId: string,
    input: { name?: string; credits?: number; price_cents?: number; is_active?: boolean },
  ) => apiFetch<AdminCreditPackage>(`/api/v1/admin/credit-packages/${packageId}`, { method: "PATCH", body: input }),

  affiliateClicks: (params: { limit?: number; offset?: number } = {}) =>
    apiFetch<AdminAffiliateClick[]>(`/api/v1/admin/affiliate-clicks${qs(params)}`),
  aiUsage: (params: { limit?: number; offset?: number } = {}) =>
    apiFetch<AdminAIUsage[]>(`/api/v1/admin/ai-usage${qs(params)}`),
  auditLog: (params: { limit?: number; offset?: number } = {}) =>
    apiFetch<Page<AdminAuditEntry>>(`/api/v1/admin/audit-log${qs(params)}`),

  // Plain arrays of ad-hoc row shapes (see api/v1/endpoints/admin.py).
  subscriptions: (params: { limit?: number; offset?: number } = {}) =>
    apiFetch<Record<string, unknown>[]>(`/api/v1/admin/subscriptions${qs(params)}`),
  payments: (params: { limit?: number; offset?: number } = {}) =>
    apiFetch<Record<string, unknown>[]>(`/api/v1/admin/payments${qs(params)}`),
};

/* -------------------------------- wardrobe --------------------------------- */

export const wardrobe = {
  list: () => apiFetch<WardrobeItem[]>("/api/v1/wardrobe"),
  create: (input: WardrobeItemInput) =>
    apiFetch<WardrobeItem>("/api/v1/wardrobe", { method: "POST", body: input }),
  update: (itemId: string, input: Partial<WardrobeItemInput>) =>
    apiFetch<WardrobeItem>(`/api/v1/wardrobe/${itemId}`, { method: "PATCH", body: input }),
  remove: (itemId: string) =>
    apiFetch<{ detail: string }>(`/api/v1/wardrobe/${itemId}`, { method: "DELETE" }),
  uploadPhoto: (itemId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<WardrobeItem>(`/api/v1/wardrobe/${itemId}/photo`, {
      method: "POST",
      body: form,
      isFormData: true,
    });
  },
};

/* ------------------------------ subscriptions ------------------------------- */

export const subscriptions = {
  plans: () => apiFetch<SubscriptionPlanOut[]>("/api/v1/subscriptions/plans"),
  me: () => apiFetch<Subscription | null>("/api/v1/subscriptions/me"),
  subscribe: (plan: SubscriptionPlanId) =>
    apiFetch<SubscribeResponse>("/api/v1/subscriptions/subscribe", { method: "POST", body: { plan } }),
  cancel: () => apiFetch<{ detail: string }>("/api/v1/subscriptions/cancel", { method: "POST" }),
};

/* --------------------------------- stylist --------------------------------- */

export const stylist = {
  ask: (input: StylistAskInput) =>
    apiFetch<StylistResponse>("/api/v1/stylist/ask", { method: "POST", body: input }),
  history: () => apiFetch<StylistResponse[]>("/api/v1/stylist/history"),
  // tap-to-ask prompts built from the user's saved preferences (empty if none)
  suggestions: () => apiFetch<{ prompts: string[] }>("/api/v1/stylist/suggestions"),
};

/* ------------------------------- saved looks -------------------------------- */

export const savedLooks = {
  list: () => apiFetch<SavedLook[]>("/api/v1/users/me/saved-looks"),
  save: (tryonResultId: string, title?: string) =>
    apiFetch<{ id: string }>(
      `/api/v1/users/me/saved-looks/${tryonResultId}${title ? `?title=${encodeURIComponent(title)}` : ""}`,
      { method: "POST" },
    ),
  remove: (lookId: string) =>
    apiFetch<{ detail: string }>(`/api/v1/users/me/saved-looks/${lookId}`, { method: "DELETE" }),
};

/* ------------------------------- preferences -------------------------------- */

export const preferences = {
  get: () => apiFetch<UserPreference>("/api/v1/users/me/preferences"),
  update: (input: Partial<UserPreference>) =>
    apiFetch<UserPreference>("/api/v1/users/me/preferences", { method: "PUT", body: input }),
};

/* ---------------------------- catalog & feed ----------------------------- */

export const catalog = {
  taxonomy: () => apiFetch<{ audiences: TaxonomyNode[] }>("/api/v1/catalog/taxonomy", { cache: "force-cache" }),
};

export const feed = {
  // Live retailer results for the categories picked in onboarding;
  // `node` narrows to one of them, omitted = a mix of all.
  forYou: (node?: string) => apiFetch<ForYouFeed>(`/api/v1/feed/for-you${qs({ node })}`),
};

/* --------------------------------- outfits --------------------------------- */

export const outfits = {
  list: () => apiFetch<Outfit[]>("/api/v1/outfits"),
  get: (outfitId: string) => apiFetch<Outfit>(`/api/v1/outfits/${outfitId}`),
  create: (input: { name?: string; occasion?: string; items: OutfitItemInput[] }) =>
    apiFetch<Outfit>("/api/v1/outfits", { method: "POST", body: input }),
  remove: (outfitId: string) =>
    apiFetch<{ detail: string }>(`/api/v1/outfits/${outfitId}`, { method: "DELETE" }),
  previewCompatibility: (items: OutfitItemInput[]) =>
    apiFetch<CompatibilityPreview>("/api/v1/outfits/preview-compatibility", {
      method: "POST",
      body: { items },
    }),
};

/* --------------------------------- try-on ---------------------------------- */

/** share and earn: your invite link and what it earned; a new account says which link it came from */
export type ReferralSummary = {
  code: string;
  /** for friends: tryonu.app/?ref=… */
  link: string;
  /** for shops: tryonu.app/sell?ref=… */
  store_link: string;
  /** extra, when a friend first buys credits (0 = off) */
  reward_credits: number;
  /** when a friend does their first try-on */
  tryon_credits: number;
  /** when a shop from your link buys its first plan */
  store_rewards: { plan: string; credits: number }[];
  friends_joined: number;
  friends_tried: number;
  friends_bought: number;
  stores_bought: number;
  credits_earned: number;
};
export type AdminReferral = {
  id: string;
  inviter_email: string;
  friend_email: string;
  source: string;
  joined_at: string;
  tried_on_at: string | null;
  store_plan: string | null;
  store_bought_at: string | null;
  credits_earned: number;
};
export const referrals = {
  me: () => apiFetch<ReferralSummary>("/api/v1/referrals/me"),
  claim: (ref: string) => apiFetch<{ claimed: boolean }>("/api/v1/referrals/claim", { method: "POST", body: { ref } }),
};
export const adminReferrals = {
  list: () =>
    apiFetch<{ invites: number; tried_on: number; stores_bought: number; credits_paid: number; rows: AdminReferral[] }>(
      "/api/v1/admin/referrals",
    ),
};

/** the browser extensions: connect this browser, see and disconnect connected ones */
export type ExtensionKind = "shopper" | "store";
export type ConnectedBrowser = { id: string; kind: ExtensionKind; label: string | null; created_at: string; last_used_at: string | null };
export const extension = {
  connect: (kind: ExtensionKind, label: string) =>
    apiFetch<{ token: string }>("/api/v1/extension/token", { method: "POST", body: { kind, label } }),
  list: () => apiFetch<ConnectedBrowser[]>("/api/v1/extension/tokens"),
  disconnectAll: () => apiFetch<void>("/api/v1/extension/tokens", { method: "DELETE" }),
};

/** the Contact page, and the admin inbox it fills */
export type ContactTopic = "general" | "tryon" | "store" | "developer" | "partnership" | "privacy";
export type ContactMessage = {
  id: string;
  name: string;
  email: string;
  topic: ContactTopic;
  topic_label: string;
  message: string;
  created_at: string;
  handled_at: string | null;
};
export const contact = {
  send: (input: { name: string; email: string; topic: ContactTopic; message: string }) =>
    apiFetch<{ detail: string }>("/api/v1/contact", { method: "POST", body: input }),
};
export const adminMessages = {
  list: (show: "open" | "all" = "open") => apiFetch<ContactMessage[]>(`/api/v1/admin/messages?show=${show}`),
  count: () => apiFetch<{ open: number }>("/api/v1/admin/messages/count"),
  handled: (id: string, undo = false) =>
    apiFetch<ContactMessage>(`/api/v1/admin/messages/${id}/handled${undo ? "?undo=true" : ""}`, { method: "POST" }),
};

/** a look someone shared: the visitor tries the same products on themselves */
export const shared = {
  tryThis: (token: string) =>
    apiFetch<{ outfit_id: string | null; product_id: string | null }>(
      `/api/v1/shared/${encodeURIComponent(token)}/try`,
      { method: "POST" },
    ),
};

export const tryon = {
  create: (input: {
    user_photo_id: string;
    product_id?: string;
    outfit_id?: string;
    wardrobe_item_id?: string;
    // The "other options" shown alongside each selected item, keyed by
    // that item's product id — see DistractorOption's own comment.
    distractor_options?: Record<string, DistractorOption[]>;
    // add these products onto this finished look (a further round)
    base_job_id?: string;
    // a free try-on paid by a TryOnU store, the picture shared with that store
    use_store_credit?: boolean;
  }) => apiFetch<TryOnJob>("/api/v1/tryon", { method: "POST", body: input }),

  /** share a finished look as a public link (same link until sharing stops) */
  share: (jobId: string) =>
    apiFetch<{ token: string; url: string; views: number }>(`/api/v1/tryon/${jobId}/share`, { method: "POST" }),
  stopSharing: (jobId: string) => apiFetch<void>(`/api/v1/tryon/${jobId}/share`, { method: "DELETE" }),

  /** the store that would pay for trying on this product or look */
  sponsor: (target: { product_id?: string; outfit_id?: string }) =>
    apiFetch<TryOnSponsor>(
      `/api/v1/tryon/sponsor?${new URLSearchParams(Object.entries(target).filter(([, v]) => !!v) as [string, string][])}`,
    ),

  // One job per photo angle (e.g. front + back) — same product/outfit,
  // charged per job. See POST /tryon/multi.
  createMulti: (input: {
    user_photo_ids: string[];
    product_id?: string;
    outfit_id?: string;
    wardrobe_item_id?: string;
    distractor_options?: Record<string, DistractorOption[]>;
  }) => apiFetch<TryOnJob[]>("/api/v1/tryon/multi", { method: "POST", body: input }),

  get: (jobId: string) => apiFetch<TryOnJob>(`/api/v1/tryon/${jobId}`),

  list: () => apiFetch<Page<TryOnJob>>("/api/v1/tryon"),

  cancel: (jobId: string) => apiFetch<TryOnJob>(`/api/v1/tryon/${jobId}/cancel`, { method: "POST" }),
};

/* -------------------------------- affiliate --------------------------------- */

export const affiliate = {
  click: (input: { product_id: string; source?: string; session_id?: string }) =>
    apiFetch<{ redirect_url: string }>("/api/v1/affiliate/click", { method: "POST", body: input }),
};

export type { Product, TryOnJob, User };

/* ------------------------------------------------------------ company stores */

type PlanPurchase = { payment_id: string; status: string; checkout_url: string | null };

export const stores = {
  plans: () => apiFetch<StorePlan[]>("/api/v1/stores/plans"),
  mine: () => apiFetch<Store>("/api/v1/stores/me"),
  create: (input: { name: string; country: string; description?: string; website_url?: string; contact_email?: string }) =>
    apiFetch<Store>("/api/v1/stores", { method: "POST", body: input }),
  update: (
    input: Partial<Pick<Store, "name" | "country" | "description" | "website_url" | "contact_email" | "delivery" | "delivery_countries">>,
  ) =>
    apiFetch<Store>("/api/v1/stores/me", { method: "PATCH", body: input }),
  uploadLogo: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<Store>("/api/v1/stores/me/logo", { method: "POST", body: form, isFormData: true });
  },
  buyPlan: (code: string) => apiFetch<PlanPurchase>(`/api/v1/stores/me/plans/${code}/purchase`, { method: "POST" }),
  subscribePlan: (code: string) =>
    apiFetch<{ checkout_url: string }>(`/api/v1/stores/me/plans/${code}/subscribe`, { method: "POST" }),
  syncSubscription: () => apiFetch<{ result: string; store: Store }>("/api/v1/stores/me/subscription/sync", { method: "POST" }),
  cancelSubscription: () => apiFetch<Store>("/api/v1/stores/me/subscription/cancel", { method: "POST" }),
  products: () => apiFetch<StoreProduct[]>("/api/v1/stores/me/products"),
  addProduct: (input: StoreProductInput) => apiFetch<StoreProduct>("/api/v1/stores/me/products", { method: "POST", body: input }),
  editProduct: (id: string, input: Partial<StoreProductInput>) =>
    apiFetch<StoreProduct>(`/api/v1/stores/me/products/${id}`, { method: "PATCH", body: input }),
  deleteProduct: (id: string) => apiFetch<void>(`/api/v1/stores/me/products/${id}`, { method: "DELETE" }),
  addImage: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<StoreProduct>(`/api/v1/stores/me/products/${id}/images`, { method: "POST", body: form, isFormData: true });
  },
  removeImage: (id: string, index: number) =>
    apiFetch<StoreProduct>(`/api/v1/stores/me/products/${id}/images/${index}`, { method: "DELETE" }),
  setFeed: (feed_url: string | null) => apiFetch<Store>("/api/v1/stores/me/feed", { method: "PUT", body: { feed_url } }),
  importFeed: () => apiFetch<{ result: string }>("/api/v1/stores/me/feed/import", { method: "POST" }),
  importFile: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<{ result: string }>("/api/v1/stores/me/products/import-file", { method: "POST", body: form, isFormData: true });
  },
  stats: () => apiFetch<StoreStats>("/api/v1/stores/me/stats"),
  payments: () => apiFetch<StorePayment[]>("/api/v1/stores/me/payments"),
  tryons: () => apiFetch<StoreTryOns>("/api/v1/stores/me/tryons"),
  publicStore: (slug: string) => apiFetch<PublicStore>(`/api/v1/stores/public/${encodeURIComponent(slug)}`),
  selectProduct: (slug: string, productId: string) =>
    apiFetch<{ product_id: string }>(`/api/v1/stores/public/${encodeURIComponent(slug)}/products/${productId}/select`, {
      method: "POST",
    }),
};

export const adminStores = {
  costs: () => apiFetch<StoreCosts>("/api/v1/admin/stores/costs"),
  adjustTryonCredits: (id: string, amount: number) =>
    apiFetch<AdminStoreDetail>(`/api/v1/admin/stores/${id}/tryon-credits`, { method: "POST", body: { amount } }),
  list: (status?: string) =>
    apiFetch<AdminStore[]>(`/api/v1/admin/stores${status ? `?status_filter=${encodeURIComponent(status)}` : ""}`),
  setStatus: (id: string, status: string, note?: string) =>
    apiFetch<AdminStore>(`/api/v1/admin/stores/${id}/status`, { method: "POST", body: { status, note: note || null } }),
  plans: () => apiFetch<StorePlan[]>("/api/v1/admin/stores/plans"),
  updatePlan: (id: string, input: Partial<Pick<StorePlan, "name" | "price_cents" | "product_limit" | "featured_limit" | "tryon_credits" | "referral_credits" | "duration_days" | "is_active">>) =>
    apiFetch<StorePlan>(`/api/v1/admin/stores/plans/${id}`, { method: "PATCH", body: input }),
  summary: () => apiFetch<AdminStoreSummary>("/api/v1/admin/stores/summary"),
  detail: (id: string) => apiFetch<AdminStoreDetail>(`/api/v1/admin/stores/${id}`),
  grantPlan: (id: string, plan_code: string, days: number) =>
    apiFetch<AdminStoreDetail>(`/api/v1/admin/stores/${id}/plan`, { method: "POST", body: { plan_code, days } }),
  endPlan: (id: string) => apiFetch<AdminStoreDetail>(`/api/v1/admin/stores/${id}/plan/end`, { method: "POST" }),
  setProductActive: (id: string, productId: string, is_active: boolean) =>
    apiFetch<AdminStoreDetail>(`/api/v1/admin/stores/${id}/products/${productId}`, { method: "PATCH", body: { is_active } }),
  deleteProduct: (id: string, productId: string) =>
    apiFetch<AdminStoreDetail>(`/api/v1/admin/stores/${id}/products/${productId}`, { method: "DELETE" }),
};


/* ------------------------------------------------------- admin operations */

export type FashnApproval = {
  live_generation_allowed: boolean;
  /** FASHN credits shoppers' try-ons can still use right now (automatic + manual) */
  credits_left_now?: number;
  automatic?: { daily_credits: number; used_today: number; left_today: number; paused: boolean };
  max_credits_per_authorization: number;
  max_hours: number;
  counted_as_spent_credits_all_time: number;
  open_authorizations: { id: string; budget: number; reserved: number; expires_at: string }[];
};

export const adminOps = {
  refundPayment: (id: string, mode: "paypal" | "mark") =>
    apiFetch<{ status: string; paypal_status: string | null; credits_removed: number; plan_days_removed: number }>(
      `/api/v1/admin/payments/${id}/refund`,
      { method: "POST", body: { mode } },
    ),
  fashnStatus: () => apiFetch<FashnApproval>("/api/v1/admin/fashn/approval"),
  fashnApprove: (credits: number, hours: number, phrase: string) =>
    apiFetch<FashnApproval>("/api/v1/admin/fashn/approval", { method: "POST", body: { credits, hours, phrase } }),
  fashnClose: () => apiFetch<FashnApproval>("/api/v1/admin/fashn/approval/close", { method: "POST" }),
  fashnResume: () => apiFetch<FashnApproval>("/api/v1/admin/fashn/approval/resume", { method: "POST" }),
};

/* ----------------------------------------------------------- developer API */

export const developers = {
  open: (input: { company_name: string; website?: string | null }) =>
    apiFetch<DeveloperAccount>("/api/v1/developers", { method: "POST", body: input }),
  mine: () => apiFetch<DeveloperAccount>("/api/v1/developers/me"),
  keys: () => apiFetch<DeveloperApiKey[]>("/api/v1/developers/keys"),
  makeKey: (input: { name: string; kind?: "secret" | "public"; allowed_domains?: string[] }) =>
    apiFetch<DeveloperApiKeyCreated>("/api/v1/developers/keys", { method: "POST", body: input }),
  revokeKey: (id: string) => apiFetch<DeveloperApiKey>(`/api/v1/developers/keys/${id}`, { method: "DELETE" }),
  packs: () => apiFetch<DeveloperCreditPack[]>("/api/v1/developers/packs"),
  buyPack: (code: string) =>
    apiFetch<{ payment_id: string; status: string; checkout_url?: string | null; developer_tryons?: number | null }>(
      `/api/v1/developers/packs/${code}/purchase`,
      { method: "POST" },
    ),
  usage: () => apiFetch<DeveloperUsage[]>("/api/v1/developers/usage"),
  payments: () => apiFetch<DeveloperPayment[]>("/api/v1/developers/payments"),
};

export const adminDevelopers = {
  list: () => apiFetch<AdminDeveloper[]>("/api/v1/admin/developers"),
  adjustCredits: (id: string, amount: number) =>
    apiFetch<DeveloperAccount>(`/api/v1/admin/developers/${id}/credits`, { method: "POST", body: { amount } }),
  setStatus: (id: string, status: "active" | "suspended") =>
    apiFetch<DeveloperAccount>(`/api/v1/admin/developers/${id}/status`, { method: "POST", body: { status } }),
  packs: () => apiFetch<DeveloperCreditPack[]>("/api/v1/admin/developers/packs"),
  updatePack: (id: string, input: Partial<Pick<DeveloperCreditPack, "name" | "tryons" | "price_cents" | "is_active">>) =>
    apiFetch<DeveloperCreditPack>(`/api/v1/admin/developers/packs/${id}`, { method: "PATCH", body: input }),
};
