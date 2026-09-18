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
  FittingProfileStatus,
  ForYouFeed,
  LiveProduct,
  Outfit,
  OutfitItemInput,
  Page,
  Product,
  ProductSearchParams,
  SavedLook,
  StylistAskInput,
  StylistResponse,
  Subscription,
  SubscribeResponse,
  SubscriptionPlanId,
  SubscriptionPlanOut,
  TaxonomyNode,
  TryOnJob,
  User,
  UserPhoto,
  UserPreference,
  WardrobeItem,
  WardrobeItemInput,
} from "./types";

/* ---------------------------------- auth --------------------------------- */

export const auth = {
  register: (input: { email: string; password: string; full_name?: string }) =>
    apiFetch<AuthResponse>("/api/v1/auth/register", { method: "POST", body: input }),

  login: (input: { email: string; password: string }) =>
    apiFetch<AuthResponse>("/api/v1/auth/login", { method: "POST", body: input }),

  logout: () => apiFetch<{ detail: string }>("/api/v1/auth/logout", { method: "POST" }),

  me: () => apiFetch<User>("/api/v1/auth/me"),

  googleLoginUrl: (apiBase: string) => `${apiBase}/api/v1/auth/google/login`,

  forgotPassword: (input: { email: string }) =>
    apiFetch<{ detail: string }>("/api/v1/auth/forgot-password", { method: "POST", body: input }),

  resetPassword: (input: { token: string; new_password: string }) =>
    apiFetch<{ detail: string }>("/api/v1/auth/reset-password", { method: "POST", body: input }),

  verifyEmail: (input: { token: string }) =>
    apiFetch<{ detail: string }>("/api/v1/auth/verify-email", { method: "POST", body: input }),

  resendVerification: () =>
    apiFetch<{ detail: string }>("/api/v1/auth/resend-verification", { method: "POST" }),
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
  purchase: (input: { credit_package_id: string }) =>
    apiFetch<{
      payment_id: string;
      status: string;
      client_secret: string | null;
      checkout_url: string | null;
      credits_granted: number | null;
      new_balance: number | null;
    }>("/api/v1/credits/purchase", { method: "POST", body: input }),
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

export const tryon = {
  create: (input: { user_photo_id: string; product_id?: string; outfit_id?: string; wardrobe_item_id?: string }) =>
    apiFetch<TryOnJob>("/api/v1/tryon", { method: "POST", body: input }),

  // One job per photo angle (e.g. front + back) — same product/outfit,
  // charged per job. See POST /tryon/multi.
  createMulti: (input: {
    user_photo_ids: string[];
    product_id?: string;
    outfit_id?: string;
    wardrobe_item_id?: string;
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
