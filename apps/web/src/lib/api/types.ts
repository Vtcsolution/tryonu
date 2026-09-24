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
  email_verified: boolean;
  credits_balance: number;
  created_at: string;
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
};

export type CreditPackage = {
  id: string;
  name: string;
  credits: number;
  price_cents: number;
  currency: string;
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
