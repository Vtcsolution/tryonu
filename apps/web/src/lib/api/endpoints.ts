import { apiFetch } from "./client";
import type {
  AdminOverview,
  AuthResponse,
  CompatibilityPreview,
  CreditBalance,
  CreditPackage,
  CreditTransaction,
  FittingProfileStatus,
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
  users: (limit = 50, offset = 0) => apiFetch<Page<User>>(`/api/v1/admin/users?limit=${limit}&offset=${offset}`),
  // These come back as plain arrays of ad-hoc row shapes (see api/v1/endpoints/admin.py) —
  // typed loosely here since the dashboard just renders known fields off each row.
  subscriptions: () => apiFetch<Record<string, unknown>[]>("/api/v1/admin/subscriptions"),
  payments: () => apiFetch<Record<string, unknown>[]>("/api/v1/admin/payments"),
  retailers: () => apiFetch<Record<string, unknown>[]>("/api/v1/admin/retailers"),
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

/* --------------------------------- outfits --------------------------------- */

export const outfits = {
  list: () => apiFetch<Outfit[]>("/api/v1/outfits"),
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
  create: (input: { user_photo_id: string; product_id?: string; outfit_id?: string }) =>
    apiFetch<TryOnJob>("/api/v1/tryon", { method: "POST", body: input }),

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
