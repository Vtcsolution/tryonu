/** Mirrors apps/api/app/schemas/*.py — keep in sync by hand for now; a
 * generated client (openapi-typescript against /openapi.json) is the
 * natural next step once the schema stabilizes. */

export type Gender = "men" | "women" | "unisex" | "kids";
export type Availability = "in_stock" | "out_of_stock" | "discontinued";
export type JobStatus = "queued" | "processing" | "completed" | "failed" | "cancelled";
export type PhotoKind =
  | "front"
  | "full_body"
  | "left_side"
  | "right_side"
  | "left_45"
  | "right_45"
  | "back"
  | "extra";

export type User = {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  auth_provider: "local" | "google";
  is_admin: boolean;
  /** a TryOnU team member: makes and publishes Ready looks */
  is_team?: boolean;
  email_verified: boolean;
  credits_balance: number;
  created_at: string;
  /** false for an account made with Google that has no password yet */
  has_password?: boolean;
  /** two-step sign-in is on */
  totp_enabled?: boolean;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type Retailer = {
  id: string;
  slug: string;
  name: string;
  logo_url: string | null;
};

export type ProductImage = {
  url: string;
  position: number;
  is_primary: boolean;
};

export type Product = {
  id: string;
  name: string;
  brand: string | null;
  // Set only for aggregator-network retailers (Rakuten, CJ) where the
  // network itself isn't the seller — null for direct retailers (eBay, ...).
  merchant_name: string | null;
  description: string | null;
  category_id: string | null;
  subcategory: string | null;
  gender: Gender;
  color: string | null;
  sizes: string[] | null;
  style_tags: string[] | null;
  price_cents: number;
  currency: string;
  rating: number | null;
  rating_count: number;
  availability: Availability;
  product_url: string;
  images: ProductImage[];
  retailer: Retailer;
  created_at: string;
};

// A search result fetched live from a retailer API — never has an `id`,
// since it isn't saved to our database yet. Select it via
// products.selectLive() first, which persists it and returns a real
// Product with an id, before it can be used for a try-on/outfit.
export type LiveProduct = {
  retailer_slug: string;
  retailer_product_id: string;
  name: string;
  brand: string | null;
  merchant_name: string | null;
  description: string | null;
  subcategory: string | null;
  gender: string;
  color: string | null;
  sizes: string[];
  style_tags: string[];
  price_cents: number;
  currency: string;
  rating: number | null;
  rating_count: number;
  availability: string;
  product_url: string;
  images: string[];
  retailer_name: string;
  /** a TryOnU store's featured product */
  featured?: boolean;
  // The exact query that found this result — pass back as-is to
  // products.selectLive() to persist this specific item. Null from plain
  // browse search (the caller already knows what it searched); set for
  // AI-stylist alternatives.
  search_term: string | null;
};

export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type UserPhoto = {
  id: string;
  kind: PhotoKind;
  url: string;
  width: number | null;
  height: number | null;
  is_primary: boolean;
  created_at: string;
};

export type FittingProfileStatus = {
  photos: UserPhoto[];
  has_front: boolean;
  has_full_body: boolean;
  is_ready: boolean;
  min_required: number;
};

/** One item on a finished try-on: where the pipeline actually put it.
 * `box` is [x0, y0, x1, y1] in fractions of the image. */
export type ResultPlacement = {
  name: string;
  product_id: string | null;
  slot: string | null;
  /** The retailer's own product photo. Absent on results rendered before
   *  it was recorded, which fall back to a crop of the render. */
  image_url?: string | null;
  drawn: boolean;
  box: number[] | null;
};

export type TryOnResult = {
  id: string;
  image_url: string;
  width: number | null;
  height: number | null;
  placements: ResultPlacement[] | null;
};

export type TryOnJob = {
  id: string;
  status: JobStatus;
  provider: string;
  provider_model: string;
  credit_cost: number;
  error_message: string | null;
  /** What the render is doing at this moment, while it runs. */
  progress: string | null;
  product: Product | null;
  outfit: Outfit | null;
  wardrobe_item: WardrobeItem | null;
  result: TryOnResult | null;
  user_photo: UserPhoto;
  /** The finished look this job added products onto, and which round of
   *  that look it is (1 = a fresh look). */
  base_job_id: string | null;
  look_round: number;
  max_look_rounds: number;
  queued_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
};

export type CreditBalance = { balance: number };

export type CreditTransaction = {
  id: string;
  amount: number;
  balance_after: number;
  reason: string;
  reference_type: string | null;
  reference_id: string | null;
  note: string | null;
  created_at: string;
};

export type OutfitItem = {
  id: string;
  slot: string;
  position: number;
  product: Product;
};

export type OutfitSlot =
  | "top"
  | "bottom"
  | "dress"
  | "outerwear"
  | "shoes"
  | "watch"
  | "bag"
  | "accessory"
  | "other";

export type Outfit = {
  id: string;
  name: string | null;
  occasion: string | null;
  created_by_stylist: boolean;
  items: OutfitItem[];
  total_price_cents: number;
  compatibility_score: number | null;
  compatibility_notes: string[] | null;
  created_at: string;
  // items the configured try-on model actually draws on the photo; the rest are shown alongside
  rendered_item_ids: string[];
};

export type OutfitItemInput = {
  product_id: string;
  slot: OutfitSlot;
};

export type CompatibilityPreview = {
  overall: number;
  color: number;
  style: number;
  notes: string[];
};

export type StylistResponse = {
  id: string;
  prompt: string;
  summary: string;
  products: Product[];
  outfit: Outfit | null;
  // Real alternatives at other price points, keyed by the recommended
  // product's id (single-product pick or outfit item) — fetched live
  // alongside the pick itself. Empty for /stylist/history replays.
  alternatives: Record<string, LiveProduct[]>;
  created_at: string;
};

// The "other options" the shopper actually saw next to a selected item,
// sent to the try-on job at creation time — the real distractor set for
// the backend's shadow-mode identity check, in preference to its own
// same-category guess. product_id is null for a live search result that
// was only ever shown, never persisted via products.selectLive().
export type DistractorOption = {
  product_id: string | null;
  image_url: string;
};

export type StylistAskInput = {
  prompt: string;
  occasion?: string;
  budget_min_cents?: number;
  budget_max_cents?: number;
  style?: string;
  max_items?: number;
  wardrobe_item_id?: string;
};

export type SavedLook = {
  id: string;
  title: string | null;
  image_url: string | null;
  product: Product | null;
  created_at: string;
  /** the try-on behind it: what Share shares */
  tryon_job_id?: string | null;
  /** every product in the look (an outfit's too) */
  items?: {
    id: string;
    name: string;
    price_cents: number;
    currency: string;
    image_url: string | null;
    shop: string | null;
    on_photo?: boolean | null;
  }[];
  total_cents?: number | null;
  currency?: string | null;
};

export type UserPreference = {
  gender: Gender | null;
  // ids from the onboarding category tree (see catalog.taxonomy())
  preferred_categories: string[] | null;
  preferred_sizes: string[] | null;
  preferred_colors: string[] | null;
  preferred_styles: string[] | null;
  preferred_brands: string[] | null;
  favorite_retailers: string[] | null;
  budget_min_cents: number | null;
  budget_max_cents: number | null;
  /** ISO alpha-2: stores from this country are shown first */
  country?: string | null;
  /** where they like to shop: local shops first, worldwide stores first, or both */
  shop_from?: ShopFrom | null;
};

export type ShopFrom = "local" | "worldwide" | "both";

export type CreditPackage = {
  id: string;
  name: string;
  credits: number;
  price_cents: number;
  currency: string;
  /** a first-purchase offer (the $1 first outfit) */
  new_members_only?: boolean;
};

export type SubscriptionPlanId = "starter" | "pro" | "business";

export type SubscriptionPlanOut = {
  plan: SubscriptionPlanId;
  name: string;
  price_cents: number;
  currency: string;
  credits_per_cycle: number;
};

export type Subscription = {
  id: string;
  plan: SubscriptionPlanId | "free";
  status: "incomplete" | "active" | "trialing" | "past_due" | "canceled";
  credits_per_cycle: number;
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  created_at: string;
};

export type WardrobeItem = {
  id: string;
  name: string;
  category: string | null;
  color: string | null;
  brand: string | null;
  style_tags: string[] | null;
  notes: string | null;
  image_url: string | null;
  created_at: string;
};

export type WardrobeItemInput = {
  name: string;
  category?: string;
  color?: string;
  brand?: string;
  style_tags?: string[];
  notes?: string;
};

export type SubscribeResponse = {
  subscription: Subscription;
  client_secret: string | null;
};

export type AdminOverview = {
  total_users: number;
  new_users_7d: number;
  active_subscriptions: number;
  total_credits_outstanding: number;
  tryon_jobs_total: number;
  tryon_jobs_24h: number;
  tryon_jobs_failed_24h: number;
  tryon_jobs_by_status: Record<string, number>;
  total_products: number;
  active_retailers: number;
  affiliate_clicks_total: number;
  affiliate_clicks_7d: number;
  revenue_cents_total: number;
  revenue_cents_30d: number;
  revenue_cents_subscriptions_30d: number;
  revenue_cents_one_off_30d: number;
  ai_cost_usd_cents_30d: number;
  ai_calls_30d: number;
};

export type AdminUser = {
  id: string;
  email: string;
  full_name: string | null;
  auth_provider: "local" | "google";
  is_active: boolean;
  is_admin: boolean;
  is_team?: boolean;
  email_verified: boolean;
  credits_balance: number;
  last_login_at: string | null;
  created_at: string;
};

export type AdminUserDetail = {
  user: AdminUser;
  tryon_jobs_total: number;
  photos_total: number;
  wardrobe_items_total: number;
  affiliate_clicks_total: number;
  recent_transactions: CreditTransaction[];
  country?: string | null;
  recent_tryons?: {
    id: string;
    created_at: string;
    status: string;
    kind: string;
    credits: number;
    paid_by: string;
    problem: string | null;
    result_image_url: string | null;
  }[];
  payments?: {
    id: string;
    created_at: string;
    amount_cents: number;
    currency: string;
    status: string;
    what: string;
    provider?: string | null;
  }[];
  photos?: { id: string; kind: string; url: string; created_at: string }[];
  store?: { id: string; name: string; status: string; detail: string } | null;
  developer?: { id: string; name: string; status: string; detail: string } | null;
};

export type AdminTryOnJob = TryOnJob & { user_email: string | null };

export type AdminProduct = {
  id: string;
  name: string;
  brand: string | null;
  retailer_slug: string;
  retailer_name: string;
  price_cents: number;
  currency: string;
  image_url: string | null;
  product_url: string;
  is_active: boolean;
  created_at: string;
};

export type AdminRetailer = {
  slug: string;
  name: string;
  is_active: boolean;
  base_commission_pct: number | null;
  affiliate_network: string | null;
  integration_built: boolean;
  credentials_configured: boolean;
  commission_tracking_configured: boolean | null;
  saved_products: number;
};

export type AdminCreditPackage = {
  id: string;
  name: string;
  credits: number;
  price_cents: number;
  currency: string;
  is_active: boolean;
  new_members_only?: boolean;
  created_at: string;
};

export type AdminSystemStatus = {
  env: string;
  tryon_provider: string;
  fashn_model: string;
  llm_provider: string;
  payment_provider: string;
  email_provider: string;
  storage: string;
  job_queue: string;
  signup_free_credits: number;
  tryon_credit_cost: number;
  outfit_tryon_credit_cost: number;
};

export type AdminAuditEntry = {
  id: string;
  admin_email: string | null;
  action: string;
  target_type: string;
  target_id: string;
  detail: Record<string, unknown> | null;
  created_at: string;
};

export type AdminAffiliateClick = {
  id: string;
  product_id: string;
  product_name: string | null;
  retailer_name: string | null;
  user_email: string | null;
  source: string;
  created_at: string;
};

export type AdminAIUsage = {
  id: string;
  kind: string;
  provider: string;
  model: string;
  success: boolean;
  latency_ms: number | null;
  cost_usd_cents: number | null;
  created_at: string;
};

export type AdminSettingField = {
  key: string;
  label: string;
  kind: "secret" | "text" | "bool" | "int" | "choice";
  choices: string[];
  help: string;
  source: "admin" | "env" | "default";
  is_set: boolean;
  // secrets: masked tail only ("••••1234") — never the real value
  value: string | null;
  unreadable: boolean;
  warning: string | null;
};

export type AdminSettingGroup = {
  id: string;
  label: string;
  testable: boolean;
  fields: AdminSettingField[];
};

export type AdminSettings = { groups: AdminSettingGroup[] };

export type ConnectionTestResult = { ok: boolean; message: string };

export type AnalyticsBreakdown = { key: string; visitors: number; views: number };

export type AnalyticsReport = {
  days: number;
  geoip_available: boolean;
  views: number;
  visitors: number;
  sessions: number;
  signed_in_visitors: number;
  live_visitors: number;
  avg_duration_ms: number | null;
  bounce_rate: number | null;
  pages_per_session: number | null;
  daily: { date: string; views: number; visitors: number }[];
  countries: AnalyticsBreakdown[];
  devices: AnalyticsBreakdown[];
  browsers: AnalyticsBreakdown[];
  operating_systems: AnalyticsBreakdown[];
  referrers: AnalyticsBreakdown[];
  pages: { path: string; views: number; visitors: number; avg_duration_ms: number | null }[];
};

export type TaxonomyNode = {
  id: string;
  label: string;
  icon: string;
  children: TaxonomyNode[];
};

export type ForYouSection = { id: string; label: string; parent_label: string | null };

export type ForYouFeed = {
  sections: ForYouSection[];
  active: string | null;
  items: (LiveProduct & { category_id: string })[];
};

export type ProductSearchParams = {
  q?: string;
  category?: string;
  brand?: string;
  color?: string;
  gender?: Gender;
  retailer?: string;
  min_price_cents?: number;
  max_price_cents?: number;
  style?: string;
  sort?: "relevance" | "price_asc" | "price_desc" | "rating" | "newest";
  limit?: number;
  offset?: number;
};

/* ------------------------------------------------------------ company stores */

export type StorePlan = {
  id: string;
  code: string;
  name: string;
  price_cents: number;
  currency: string;
  product_limit: number;
  /** how many products a store on this plan can feature */
  featured_limit: number;
  /** shopper try-ons the store pays for, included with the plan */
  tryon_credits: number;
  /** credits for whoever invited the store, when it buys this plan */
  referral_credits?: number;
  duration_days: number;
  is_active: boolean;
};

export type Store = {
  id: string;
  name: string;
  slug: string;
  country: string;
  description: string | null;
  website_url: string | null;
  contact_email: string | null;
  /** digits with the country code: shoppers order on WhatsApp */
  whatsapp?: string | null;
  logo_url: string | null;
  /** pending | approved | rejected | suspended */
  status: string;
  status_note: string | null;
  plan_code: string | null;
  plan_product_limit: number;
  plan_expires_at: string | null;
  plan_active: boolean;
  /** the current plan was given free by an admin */
  plan_free?: boolean;
  plan_featured_limit?: number;
  featured_count?: number;
  /** domestic: its own country only | countries: plus delivery_countries | worldwide */
  delivery?: StoreDelivery;
  delivery_countries?: string[];
  /** when the store was opened on TryOnU */
  opened_at?: string | null;
  /** shopper try-ons the store can still pay for */
  tryon_credits?: number;
  live: boolean;
  product_count: number;
  feed_url: string | null;
  feed_last_run_at: string | null;
  feed_last_result: string | null;
  /** a PayPal subscription renews the plan every period */
  auto_renew: boolean;
  subscription_status: string | null;
  subscription_plan_code: string | null;
};

export type AdminStore = Store & { owner_email: string; created_at: string };

export type StoreProduct = {
  id: string;
  source: "manual" | "feed";
  name: string;
  description: string | null;
  price_cents: number;
  currency: string;
  images: string[];
  product_url: string;
  category: string | null;
  gender: string;
  color: string | null;
  is_active: boolean;
  is_featured?: boolean;
  /** null: delivered like the rest of the store */
  delivery?: "domestic" | "worldwide" | null;
  /** on a public store page: can it reach this shopper (null: unknown) */
  delivers_to_you?: boolean | null;
  updated_at: string;
};

export type StoreProductInput = {
  name: string;
  description?: string | null;
  price_cents: number;
  currency: string;
  product_url: string;
  category?: string | null;
  gender: string;
  color?: string | null;
  is_active?: boolean;
  is_featured?: boolean;
  delivery?: "domestic" | "worldwide" | null;
};


export type StoreStats = {
  days: number;
  views: number;
  clicks: number;
  tryons: number;
  /** looks with the store's products that shoppers saved */
  saves?: number;
  /** likes on community posts wearing them */
  likes?: number;
  /** shoppers waiting for a price drop */
  alerts?: number;
  top: {
    store_product_id: string;
    name: string;
    views: number;
    clicks: number;
    tryons: number;
    saves?: number;
    likes?: number;
    alerts?: number;
  }[];
};

export type StorePayment = {
  id: string;
  amount_cents: number;
  currency: string;
  status: string;
  plan_name: string | null;
  created_at: string;
};

export type StoreDelivery = "domestic" | "countries" | "worldwide";

export type PublicStore = {
  name: string;
  slug: string;
  country: string;
  delivery?: StoreDelivery;
  delivery_countries?: string[];
  description: string | null;
  website_url: string | null;
  logo_url: string | null;
  whatsapp?: string | null;
  products: StoreProduct[];
};

export type AdminStoreDetail = AdminStore & { stats: StoreStats; payments: StorePayment[]; products: StoreProduct[] };

export type AdminStoreSummary = {
  by_status: Record<string, number>;
  live: number;
  products: number;
  plan_revenue: Record<string, number>;
};

export type StoreTryOnPicture = {
  id: string;
  image_url: string;
  product_name: string;
  product_url: string | null;
  product_image: string | null;
  shopper_country: string | null;
  paid_by_store: boolean;
  created_at: string;
};

export type StoreTryOns = {
  credits_left: number;
  plan_credits: number;
  used_by_store: number;
  used_30d: number;
  tryons_total: number;
  private_tryons: number;
  products: { store_product_id: string | null; name: string; tryons: number; paid_by_store: number; shared: number }[];
  pictures: StoreTryOnPicture[];
};

export type StoreCosts = {
  fashn_credits_per_tryon: number;
  fashn_credit_pkr: number;
  usd_to_pkr: number;
  tryon_cost_usd_cents: number;
};

/** The TryOnU store that would pay for a try-on, if any. */
export type TryOnSponsor = { store_id: string | null; store_name: string | null };

/* ----------------------------------------------------------- developer API */

export type DeveloperAccount = {
  id: string;
  company_name: string;
  website: string | null;
  credits: number;
  status: "active" | "suspended";
  tryons_total: number;
  tryons_30d: number;
  created_at: string;
};

export type DeveloperApiKey = {
  id: string;
  name: string;
  /** secret: for a server | public: a website key for the widget, only on allowed_domains */
  kind: "secret" | "public";
  prefix: string;
  allowed_domains?: string[];
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string;
};

/** Returned once, when the key is made: only then is the full key known. */
export type DeveloperApiKeyCreated = DeveloperApiKey & { key: string };

export type DeveloperCreditPack = {
  id: string;
  code: string;
  name: string;
  tryons: number;
  price_cents: number;
  currency: string;
  is_active: boolean;
};

export type DeveloperUsage = {
  id: string;
  status: "queued" | "processing" | "completed" | "failed";
  reference: string | null;
  credits: number;
  refunded: boolean;
  result_image_url: string | null;
  error: string | null;
  created_at: string;
};

export type DeveloperPayment = {
  id: string;
  amount_cents: number;
  currency: string;
  status: string;
  pack_name: string | null;
  tryons: number | null;
  created_at: string;
};

export type AdminDeveloper = DeveloperAccount & { owner_email: string; keys: number };

/** A look its owner shared: what anyone with the link sees. */
export type SharedLook = {
  token: string;
  image_url: string;
  title: string;
  products: {
    id: string;
    name: string;
    price_cents: number;
    currency: string;
    image_url: string | null;
    shop: string | null;
    buy_url: string;
    /** drawn on the picture, or shown alongside as a match (null: unknown) */
    on_photo?: boolean | null;
  }[];
  total_cents?: number | null;
  currency?: string | null;
  created_at: string;
};
