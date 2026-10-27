import { API_BASE_URL, apiFetch, uploadWithProgress } from "./client";
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
  register: (input: { email: string; password: string; full_name?: string; country?: string; next?: string }) =>
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
  /** which checkout the site opens: paddle (card, PayPal, Apple Pay, Google Pay) or paypal */
  checkoutConfig: () =>
    apiFetch<{
      provider: string;
      gateways: { id: string; label: string }[];
      paddle: { token: string; environment: "sandbox" | "production" } | null;
    }>(
      "/api/v1/credits/checkout-config",
    ),
  purchase: (input: { credit_package_id: string }, gateway?: string | null) =>
    apiFetch<{
      payment_id: string;
      status: string;
      client_secret: string | null;
      checkout_url: string | null;
      credits_granted: number | null;
      new_balance: number | null;
    }>(`/api/v1/credits/purchase${gateway ? `?gateway=${encodeURIComponent(gateway)}` : ""}`, { method: "POST", body: input }),
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
  updateUser: (userId: string, input: { is_active?: boolean; is_admin?: boolean; is_team?: boolean; email_verified?: boolean }) =>
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
  createCreditPackage: (input: { name: string; credits: number; price_cents: number; currency?: string; new_members_only?: boolean }) =>
    apiFetch<AdminCreditPackage>("/api/v1/admin/credit-packages", { method: "POST", body: input }),
  updateCreditPackage: (
    packageId: string,
    input: { name?: string; credits?: number; price_cents?: number; is_active?: boolean; new_members_only?: boolean },
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

/** the community (members only): posts, likes, comments, profiles, follows, reports */
export type CommunityAuthor = { handle: string; name: string | null; avatar_url: string | null };
export type CommunityProduct = {
  id: string;
  name: string;
  price_cents: number;
  currency: string;
  image_url: string | null;
  shop: string | null;
  buy_url: string;
};
/** a song in the free music library */
export type MusicTrack = { id: string; title: string; artist: string | null; mood: string | null; url: string };
export type AdminMusicTrack = MusicTrack & { is_active: boolean; uses: number; size_bytes: number; created_at: string };

export type CommunityPost = {
  id: string;
  /** a song from the music library, played with it in Reels */
  music?: MusicTrack | null;
  author: CommunityAuthor;
  /** a try-on look, or a photo / video the member uploaded */
  media_kind?: "tryon" | "image" | "video";
  image_url: string | null;
  video_url?: string | null;
  poster_url?: string | null;
  caption: string | null;
  like_count: number;
  comment_count: number;
  liked_by_me: boolean;
  following_author: boolean;
  is_mine: boolean;
  products: CommunityProduct[];
  created_at: string;
  /** a few of the people who liked it, newest first */
  likers?: CommunityAuthor[];
  previews?: LinkPreview[];
  /** outside links taken out of the caption (only on the answer to a new post) */
  links_removed?: number;
  /** "Buy or skip?" */
  poll?: boolean;
  poll_buy?: number;
  poll_skip?: number;
  my_vote?: "buy" | "skip" | null;
  /** an entry in a style challenge, and its place if it won */
  challenge?: { id: string; title: string } | null;
  award?: number | null;
  /** bookmarked to come back to */
  saved_by_me?: boolean;
};
/** a card for a TryOnU store, product, look or post link */
export type LinkPreview = {
  url: string;
  kind: "store" | "product" | "look" | "post";
  title: string;
  subtitle: string | null;
  image_url: string | null;
  price_cents: number | null;
  currency: string | null;
};
export type CommunityComment = {
  id: string;
  author: CommunityAuthor;
  body: string;
  parent_id: string | null;
  /** the @handle this answers */
  reply_to?: string | null;
  is_mine: boolean;
  can_delete: boolean;
  created_at: string;
  like_count: number;
  liked_by_me: boolean;
  image_url: string | null;
  look: { image_url: string; products: CommunityProduct[] } | null;
  previews: LinkPreview[];
  links_removed?: number;
  replies: CommunityComment[];
};
export type NewComment = { body: string; parent_id?: string; image_key?: string; tryon_job_id?: string };
export type CommunityProfile = {
  handle: string;
  name: string | null;
  avatar_url: string | null;
  bio: string | null;
  posts: number;
  followers: number;
  following: number;
  followed_by_me: boolean;
  is_me: boolean;
  trophies?: { challenge_id: string; title: string; place: number; post_id: string | null }[];
};
export type Challenge = {
  id: string;
  title: string;
  description: string | null;
  starts_at: string;
  ends_at: string;
  state: "upcoming" | "live" | "ended";
  prizes: number[];
  sponsor: { name: string; slug: string; logo_url: string | null } | null;
  entries: number;
  my_entry_post_id: string | null;
  winners: { place: number; credits: number; likes: number; author: CommunityAuthor; post_id: string | null }[];
  hidden?: boolean;
};
export type ChallengeInput = {
  title: string;
  description?: string;
  starts_at: string;
  ends_at: string;
  prize_1: number;
  prize_2: number;
  prize_3: number;
  sponsor_store_slug?: string;
};
/** what a new post can also do: ask "Buy or skip?", enter a challenge */
export type PostExtras = { poll?: boolean; challenge_id?: string | null; music_track_id?: string | null };
export type CommunityFeed = { posts: CommunityPost[]; next_offset: number | null };
export type CommunityReportRow = {
  id: string;
  reason: string;
  reporter_email: string;
  kind: "post" | "comment";
  target_id: string;
  author_handle: string | null;
  author_email: string | null;
  text: string | null;
  image_url: string | null;
  video_url?: string | null;
  hidden: boolean;
  created_at: string;
  resolved_at: string | null;
};
const C = "/api/v1/community";
export const community = {
  feed: (tab: "for_you" | "following", offset = 0) => apiFetch<CommunityFeed>(`${C}/feed?tab=${tab}&offset=${offset}`),
  post: (id: string) => apiFetch<CommunityPost>(`${C}/posts/${id}`),
  /** the free music library members can add to a post */
  music: () => apiFetch<MusicTrack[]>(`${C}/music`),
  create: (input: { tryon_job_id: string; caption?: string; accept_rules: boolean } & PostExtras) =>
    apiFetch<CommunityPost>(`${C}/posts`, { method: "POST", body: input }),
  postForJob: (jobId: string) => apiFetch<{ post_id: string | null }>(`${C}/posts/by-job/${jobId}`),
  /** my own photo or video, with upload progress (0-100) */
  createMedia: (file: File, caption: string, onProgress: (pct: number) => void, extras: PostExtras = {}) => {
    const form = new FormData();
    form.append("file", file);
    form.append("caption", caption);
    form.append("accept_rules", "true");
    if (extras.poll) form.append("poll", "true");
    if (extras.challenge_id) form.append("challenge_id", extras.challenge_id);
    if (extras.music_track_id) form.append("music_track_id", extras.music_track_id);
    return uploadWithProgress<CommunityPost>(`${C}/posts/media`, form, onProgress);
  },
  myLooks: () =>
    apiFetch<{ job_id: string; image_url: string; saved: boolean; post_id: string | null; created_at: string }[]>(`${C}/my-looks`),
  remove: (id: string) => apiFetch<void>(`${C}/posts/${id}`, { method: "DELETE" }),
  like: (id: string) => apiFetch<{ liked: boolean; like_count: number }>(`${C}/posts/${id}/like`, { method: "POST" }),
  unlike: (id: string) => apiFetch<{ liked: boolean; like_count: number }>(`${C}/posts/${id}/like`, { method: "DELETE" }),
  vote: (id: string, choice: "buy" | "skip") =>
    apiFetch<{ my_vote: "buy" | "skip" | null; poll_buy: number; poll_skip: number }>(`${C}/posts/${id}/vote`, {
      method: "POST",
      body: { choice },
    }),
  unvote: (id: string) =>
    apiFetch<{ my_vote: "buy" | "skip" | null; poll_buy: number; poll_skip: number }>(`${C}/posts/${id}/vote`, { method: "DELETE" }),
  challenges: () => apiFetch<{ live: Challenge[]; upcoming: Challenge[]; ended: Challenge[] }>(`${C}/challenges`),
  challenge: (id: string, offset = 0) =>
    apiFetch<{ challenge: Challenge; entries: CommunityFeed }>(`${C}/challenges/${id}?offset=${offset}`),
  tryLook: (id: string) => apiFetch<{ outfit_id: string | null; product_id: string | null }>(`${C}/posts/${id}/try`, { method: "POST" }),
  comments: (id: string) => apiFetch<CommunityComment[]>(`${C}/posts/${id}/comments`),
  comment: (id: string, input: NewComment) => apiFetch<CommunityComment>(`${C}/posts/${id}/comments`, { method: "POST", body: input }),
  removeComment: (id: string) => apiFetch<void>(`${C}/comments/${id}`, { method: "DELETE" }),
  /** a photo for a comment, uploaded before the comment is posted */
  commentImage: (file: File, onProgress: (pct: number) => void) => {
    const form = new FormData();
    form.append("file", file);
    return uploadWithProgress<{ image_key: string; image_url: string }>(`${C}/comment-images`, form, onProgress);
  },
  likeComment: (id: string) => apiFetch<{ liked: boolean; like_count: number }>(`${C}/comments/${id}/like`, { method: "POST" }),
  unlikeComment: (id: string) => apiFetch<{ liked: boolean; like_count: number }>(`${C}/comments/${id}/like`, { method: "DELETE" }),
  tryCommentLook: (id: string) =>
    apiFetch<{ outfit_id: string | null; product_id: string | null }>(`${C}/comments/${id}/try`, { method: "POST" }),
  likers: (id: string) => apiFetch<CommunityAuthor[]>(`${C}/posts/${id}/likes`),
  save: (id: string) => apiFetch<{ saved: boolean }>(`${C}/posts/${id}/save`, { method: "POST" }),
  unsave: (id: string) => apiFetch<{ saved: boolean }>(`${C}/posts/${id}/save`, { method: "DELETE" }),
  saved: (offset = 0) => apiFetch<CommunityFeed>(`${C}/saved?offset=${offset}`),
  /** members to @mention: people I follow first */
  people: (q: string) => apiFetch<CommunityAuthor[]>(`${C}/people?q=${encodeURIComponent(q)}`),
  me: () => apiFetch<CommunityProfile>(`${C}/me`),
  updateMe: (input: { handle?: string; bio?: string }) => apiFetch<CommunityProfile>(`${C}/me`, { method: "PATCH", body: input }),
  uploadAvatar: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<CommunityProfile>(`${C}/me/avatar`, { method: "POST", body: form, isFormData: true });
  },
  removeAvatar: () => apiFetch<CommunityProfile>(`${C}/me/avatar`, { method: "DELETE" }),
  profile: (handle: string) => apiFetch<CommunityProfile>(`${C}/profiles/${encodeURIComponent(handle)}`),
  profilePosts: (handle: string, offset = 0) => apiFetch<CommunityFeed>(`${C}/profiles/${encodeURIComponent(handle)}/posts?offset=${offset}`),
  follow: (handle: string) => apiFetch<CommunityProfile>(`${C}/profiles/${encodeURIComponent(handle)}/follow`, { method: "POST" }),
  unfollow: (handle: string) => apiFetch<CommunityProfile>(`${C}/profiles/${encodeURIComponent(handle)}/follow`, { method: "DELETE" }),
  report: (input: { post_id?: string; comment_id?: string; reason: string }) =>
    apiFetch<{ detail: string }>(`${C}/reports`, { method: "POST", body: input }),
};
export type AdminCommunityStats = {
  members: number;
  active_7d: number;
  posts: number;
  posts_7d: number;
  comments: number;
  comments_7d: number;
  likes: number;
  likes_7d: number;
  comment_likes: number;
  follows: number;
  links_removed: number;
  hidden: number;
  blocked: number;
  open_reports: number;
};
export type AdminCommunityMember = {
  user_id: string;
  handle: string;
  name: string | null;
  email: string;
  avatar_url: string | null;
  posts: number;
  comments: number;
  likes_given: number;
  likes_received: number;
  followers: number;
  following: number;
  links_removed: number;
  last_active_at: string | null;
  blocked_at: string | null;
  joined_at: string;
};
export type AdminCommunityComment = {
  id: string;
  post_id: string;
  post_caption: string | null;
  post_author_handle: string | null;
  author: CommunityAuthor;
  author_email: string;
  author_id: string;
  body: string;
  reply_to: string | null;
  image_url: string | null;
  look_image_url: string | null;
  like_count: number;
  links_removed: number;
  hidden: boolean;
  created_at: string;
};
export type AdminCommunityPost = {
  id: string;
  author: CommunityAuthor;
  author_email: string;
  author_id: string;
  media_kind: "tryon" | "image" | "video";
  image_url: string | null;
  video_url: string | null;
  caption: string | null;
  like_count: number;
  comment_count: number;
  links_removed: number;
  hidden: boolean;
  created_at: string;
};
const AC = "/api/v1/admin/community";
export const adminCommunity = {
  reports: (show: "open" | "all" = "open") => apiFetch<CommunityReportRow[]>(`${AC}/reports?show=${show}`),
  resolve: (id: string, action: "hide" | "dismiss" | "ban") =>
    apiFetch<{ detail: string }>(`${AC}/reports/${id}/resolve`, { method: "POST", body: { action } }),
  stats: () => apiFetch<AdminCommunityStats>(`${AC}/stats`),
  members: (p: { q?: string; sort?: "engaged" | "newest" | "blocked"; offset?: number }) =>
    apiFetch<{ total: number; rows: AdminCommunityMember[] }>(`${AC}/members?${qs({ q: p.q ?? "", sort: p.sort ?? "engaged", offset: p.offset ?? 0 })}`),
  comments: (p: { q?: string; member?: string; show?: "all" | "hidden" | "links"; offset?: number }) =>
    apiFetch<{ total: number; rows: AdminCommunityComment[] }>(
      `${AC}/comments?${qs({ q: p.q ?? "", member: p.member ?? "", show: p.show ?? "all", offset: p.offset ?? 0 })}`,
    ),
  posts: (p: { member?: string; sort?: "newest" | "engaged" | "hidden"; offset?: number }) =>
    apiFetch<{ total: number; rows: AdminCommunityPost[] }>(
      `${AC}/posts?${qs({ member: p.member ?? "", sort: p.sort ?? "newest", offset: p.offset ?? 0 })}`,
    ),
  hideComment: (id: string, hidden: boolean) => apiFetch<{ hidden: boolean }>(`${AC}/comments/${id}/hidden`, { method: "POST", body: { hidden } }),
  hidePost: (id: string, hidden: boolean) => apiFetch<{ hidden: boolean }>(`${AC}/posts/${id}/hidden`, { method: "POST", body: { hidden } }),
  challenges: () => apiFetch<Challenge[]>(`${AC}/challenges`),
  createChallenge: (input: ChallengeInput) => apiFetch<Challenge>(`${AC}/challenges`, { method: "POST", body: input }),
  updateChallenge: (id: string, input: ChallengeInput) => apiFetch<Challenge>(`${AC}/challenges/${id}`, { method: "PUT", body: input }),
  finishChallenge: (id: string) => apiFetch<Challenge>(`${AC}/challenges/${id}/finish`, { method: "POST" }),
  hideChallenge: (id: string, hidden: boolean) =>
    apiFetch<Challenge>(`${AC}/challenges/${id}/hidden`, { method: "POST", body: { hidden } }),
  block: (userId: string) => apiFetch<{ detail: string }>(`${AC}/users/${userId}/ban`, { method: "POST" }),
  unblock: (userId: string) => apiFetch<{ detail: string }>(`${AC}/users/${userId}/unban`, { method: "POST" }),
};

/** your size: measurements and the size they suggest */
export type SizeSuggestion = {
  audience: "women" | "men";
  letter: string;
  uk: string | null;
  us: string | null;
  eu: string | null;
  chest_in: string | null;
  trousers_waist_in: string | null;
  shoe: { eu: string; uk: string; us: string } | null;
  basis: "measurements" | "height_weight" | "shoes_only";
  fit: string;
};
export type MySize = {
  gender: "women" | "men" | null;
  height_cm: number | null;
  weight_kg: number | null;
  bust_cm: number | null;
  waist_cm: number | null;
  hips_cm: number | null;
  shoe_eu: number | null;
  fit: "regular" | "loose" | "slim" | null;
  suggestion: SizeSuggestion | null;
};
export const mySize = {
  get: () => apiFetch<MySize>("/api/v1/users/me/size"),
  save: (input: Omit<MySize, "suggestion">) => apiFetch<MySize>("/api/v1/users/me/size", { method: "PUT", body: input }),
};

/** price alerts: told when a product gets cheaper or is back in stock */
export type PriceAlert = {
  product_id: string;
  name: string;
  image_url: string | null;
  shop: string | null;
  currency: string;
  start_price_cents: number;
  price_cents: number;
  in_stock: boolean;
  checked_at: string | null;
  created_at: string;
};
export const priceAlerts = {
  list: () => apiFetch<PriceAlert[]>("/api/v1/price-alerts"),
  ids: () => apiFetch<string[]>("/api/v1/price-alerts/ids"),
  add: (productId: string) => apiFetch<PriceAlert>(`/api/v1/price-alerts/${productId}`, { method: "POST" }),
  remove: (productId: string) => apiFetch<void>(`/api/v1/price-alerts/${productId}`, { method: "DELETE" }),
};

/** Find the look: search the shops with a photo (like Google Lens) */
export type LensMatch = { product: LiveProduct; score: number; match: "exact" | "close" | "similar" };
export type LensItem = {
  label: string;
  category: string;
  query: string;
  color: string | null;
  details: string | null;
  /** x0, y0, x1, y1 as fractions of the photo */
  box: number[];
  matches: LensMatch[];
};
export type LensResult = {
  id: string;
  image_url: string;
  width: number;
  height: number;
  summary: string | null;
  items: LensItem[];
  created_at: string;
  /** the viewer made this search (a shared link shows it to anyone) */
  mine?: boolean;
};
export type LensSummary = { id: string; image_url: string; summary: string | null; items: number; created_at: string };
export const lens = {
  search: (file: File, onProgress: (pct: number) => void) => {
    const form = new FormData();
    form.append("file", file);
    return uploadWithProgress<LensResult>("/api/v1/lens", form, onProgress);
  },
  from: (input: { tryon_job_id?: string; post_id?: string }) => apiFetch<LensResult>("/api/v1/lens/from", { method: "POST", body: input }),
  list: () => apiFetch<LensSummary[]>("/api/v1/lens"),
  get: (id: string) => apiFetch<LensResult>(`/api/v1/lens/${id}`),
  remove: (id: string) => apiFetch<void>(`/api/v1/lens/${id}`, { method: "DELETE" }),
};

/** the bell: notifications, the daily-email setting, phones that want notifications */
export type AppNotification = {
  id: string;
  kind: "post_like" | "comment" | "reply" | "comment_like" | "follow" | "referral_joined" | "reward" | "credits_added" | string;
  text: string;
  url: string;
  actor: { handle: string | null; name: string | null; avatar_url: string | null } | null;
  image_url: string | null;
  credits: number | null;
  read: boolean;
  created_at: string;
};
export type NotificationSettings = { email: boolean; push_key: string | null; phones: number };
const N = "/api/v1/notifications";
export const notifications = {
  list: (offset = 0, limit = 20) =>
    apiFetch<{ items: AppNotification[]; unread: number; next_offset: number | null }>(`${N}?offset=${offset}&limit=${limit}`),
  unread: () => apiFetch<{ unread: number }>(`${N}/unread-count`),
  read: (id: string) => apiFetch<{ unread: number }>(`${N}/${id}/read`, { method: "POST" }),
  readAll: () => apiFetch<{ unread: number }>(`${N}/read-all`, { method: "POST" }),
  settings: () => apiFetch<NotificationSettings>(`${N}/settings`),
  setEmail: (email: boolean) => apiFetch<NotificationSettings>(`${N}/settings`, { method: "PATCH", body: { email } }),
  addPhone: (sub: { endpoint: string; keys: { p256dh: string; auth: string } }) =>
    apiFetch<NotificationSettings>(`${N}/push`, { method: "POST", body: sub }),
  removePhone: (endpoint: string) => apiFetch<NotificationSettings>(`${N}/push/remove`, { method: "POST", body: { endpoint } }),
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
  /** the help WhatsApp number (digits with the country code), when an admin set one */
  info: () => apiFetch<{ whatsapp: string | null }>("/api/v1/contact/info"),
  send: (input: { name: string; email: string; topic: ContactTopic; message: string }) =>
    apiFetch<{ detail: string }>("/api/v1/contact", { method: "POST", body: input }),
};
export type Announcement = { id: string; text: string; url: string | null; sent_to: number; created_at: string };
export const adminAnnouncements = {
  list: () => apiFetch<{ members: number; items: Announcement[] }>("/api/v1/admin/announcements"),
  send: (input: { text: string; url?: string }) =>
    apiFetch<Announcement>("/api/v1/admin/announcements", { method: "POST", body: input }),
};

/** Whether a product can be ordered on WhatsApp (local stores that take WhatsApp orders). */
export const orderOptions = (productId: string) => apiFetch<{ whatsapp: boolean }>(`/api/v1/affiliate/order-options/${productId}`);
/** Opens WhatsApp with the store, the order message already written; counted as a shop click. */
export const whatsappOrderUrl = (productId: string, source: string) =>
  `${API_BASE_URL}/api/v1/affiliate/whatsapp/${productId}?source=${encodeURIComponent(source)}`;

const AM = "/api/v1/admin/community/music";
export const adminMusic = {
  list: () => apiFetch<AdminMusicTrack[]>(AM),
  add: (file: File, title: string, artist: string, mood: string, onProgress: (pct: number) => void) => {
    const form = new FormData();
    form.append("file", file);
    form.append("title", title);
    if (artist) form.append("artist", artist);
    if (mood) form.append("mood", mood);
    return uploadWithProgress<AdminMusicTrack>(AM, form, onProgress);
  },
  update: (id: string, input: Partial<Pick<AdminMusicTrack, "title" | "artist" | "mood" | "is_active">>) =>
    apiFetch<AdminMusicTrack>(`${AM}/${id}`, { method: "PATCH", body: input }),
  remove: (id: string) => apiFetch<void>(`${AM}/${id}`, { method: "DELETE" }),
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
  create: (input: { name: string; country: string; description?: string; website_url?: string; contact_email?: string; whatsapp?: string }) =>
    apiFetch<Store>("/api/v1/stores", { method: "POST", body: input }),
  update: (
    input: Partial<Pick<Store, "name" | "country" | "description" | "website_url" | "contact_email" | "whatsapp" | "delivery" | "delivery_countries">>,
  ) =>
    apiFetch<Store>("/api/v1/stores/me", { method: "PATCH", body: input }),
  uploadLogo: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<Store>("/api/v1/stores/me/logo", { method: "POST", body: form, isFormData: true });
  },
  buyPlan: (code: string, gateway?: string | null) =>
    apiFetch<PlanPurchase>(`/api/v1/stores/me/plans/${code}/purchase${gateway ? `?gateway=${encodeURIComponent(gateway)}` : ""}`, {
      method: "POST",
    }),
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
  /** every store shoppers can visit now (name and link name) */
  publicStores: () => apiFetch<{ slug: string; name: string; country: string }[]>("/api/v1/stores/public"),
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
  buyPack: (code: string, gateway?: string | null) =>
    apiFetch<{ payment_id: string; status: string; checkout_url?: string | null; developer_tryons?: number | null }>(
      `/api/v1/developers/packs/${code}/purchase${gateway ? `?gateway=${encodeURIComponent(gateway)}` : ""}`,
      { method: "POST" },
    ),
  usage: () => apiFetch<DeveloperUsage[]>("/api/v1/developers/usage"),
  payments: () => apiFetch<DeveloperPayment[]>("/api/v1/developers/payments"),
};

export const adminDevelopers = {
  list: () => apiFetch<AdminDeveloper[]>("/api/v1/admin/developers"),
  /** give API try-ons free (positive) or take some back (negative); a gift tells the developer */
  adjustCredits: (id: string, amount: number, note?: string) =>
    apiFetch<DeveloperAccount>(`/api/v1/admin/developers/${id}/credits`, { method: "POST", body: { amount, note: note || undefined } }),
  setStatus: (id: string, status: "active" | "suspended") =>
    apiFetch<DeveloperAccount>(`/api/v1/admin/developers/${id}/status`, { method: "POST", body: { status } }),
  packs: () => apiFetch<DeveloperCreditPack[]>("/api/v1/admin/developers/packs"),
  updatePack: (id: string, input: Partial<Pick<DeveloperCreditPack, "name" | "tryons" | "price_cents" | "is_active">>) =>
    apiFetch<DeveloperCreditPack>(`/api/v1/admin/developers/packs/${id}`, { method: "PATCH", body: input }),
};

/** the home page's example look: its real shop products, live from the shops */
export type ShowcaseItem = { name: string; shop: string; price_cents: number; currency: string; image_url: string; buy_url: string };
export const showcase = {
  look: (look: "women" | "men" | "kids" = "women") => apiFetch<ShowcaseItem[]>(`/api/v1/showcase/look?look=${look}`),
};

/** Ready looks (tryonu.app/looks): outfits the TryOnU team tried on a model, to try on yourself */
export type ReadyLookItem = {
  id: string;
  product_id: string;
  name: string;
  shop: string | null;
  price_cents: number;
  currency: string;
  image_url: string | null;
  buy_url: string;
};
export type ReadyLook = {
  id: string;
  title: string;
  audience: "women" | "men" | "kids";
  season: string | null;
  card_url: string;
  card_small_url: string;
  image_url: string;
  is_published: boolean;
  sort_order: number;
  items: ReadyLookItem[];
  total_cents: number | null;
  currency: string | null;
  created_by?: string | null;
  created_at?: string | null;
  // team panel only
  mine?: boolean;
  tryon_job_id?: string | null;
  community?: { post_id: string; handle: string }[];
};
/** A community profile the team posts Ready looks as. */
export type TeamPerson = { id: string; name: string; handle: string; avatar_url: string | null; posts: number };
const personForm = (input: { name?: string; handle?: string; photo?: File | null }) => {
  const form = new FormData();
  if (input.name) form.append("name", input.name);
  if (input.handle) form.append("handle", input.handle);
  if (input.photo) form.append("photo", input.photo);
  return form;
};
export const readyLooks = {
  list: (audience?: string) => apiFetch<ReadyLook[]>(`/api/v1/looks${audience ? `?audience=${audience}` : ""}`),
  get: (id: string) => apiFetch<ReadyLook>(`/api/v1/looks/${encodeURIComponent(id)}`),
  tryIt: (id: string) =>
    apiFetch<{ outfit_id: string | null; product_id: string | null }>(`/api/v1/looks/${encodeURIComponent(id)}/try`, { method: "POST" }),
};
export const team = {
  looks: () => apiFetch<ReadyLook[]>("/api/v1/team/looks"),
  publish: (input: { tryon_job_id: string; title: string; audience: string; season?: string | null; publish?: boolean }) =>
    apiFetch<ReadyLook>("/api/v1/team/looks", { method: "POST", body: input }),
  update: (id: string, input: { title?: string; audience?: string; season?: string | null; is_published?: boolean; sort_order?: number }) =>
    apiFetch<ReadyLook>(`/api/v1/team/looks/${id}`, { method: "PATCH", body: input }),
  refresh: (id: string) => apiFetch<ReadyLook>(`/api/v1/team/looks/${id}/refresh`, { method: "POST" }),
  removeItem: (id: string, itemId: string) => apiFetch<ReadyLook>(`/api/v1/team/looks/${id}/items/${itemId}`, { method: "DELETE" }),
  remove: (id: string) => apiFetch<void>(`/api/v1/team/looks/${id}`, { method: "DELETE" }),
  people: () => apiFetch<TeamPerson[]>("/api/v1/team/people"),
  addPerson: (input: { name: string; handle: string; photo: File }) =>
    apiFetch<TeamPerson>("/api/v1/team/people", { method: "POST", body: personForm(input), isFormData: true }),
  editPerson: (id: string, input: { name?: string; handle?: string; photo?: File | null }) =>
    apiFetch<TeamPerson>(`/api/v1/team/people/${id}`, { method: "PATCH", body: personForm(input), isFormData: true }),
  postToCommunity: (lookId: string, input: { person_id: string; caption?: string; poll?: boolean }) =>
    apiFetch<{ post_id: string; handle: string }>(`/api/v1/team/looks/${lookId}/community`, { method: "POST", body: input }),
};
