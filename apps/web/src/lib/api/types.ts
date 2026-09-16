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

export type TryOnResult = {
  id: string;
  image_url: string;
  width: number | null;
  height: number | null;
};

export type TryOnJob = {
  id: string;
  status: JobStatus;
  provider: string;
  provider_model: string;
  credit_cost: number;
  error_message: string | null;
  product: Product | null;
  outfit: Outfit | null;
  result: TryOnResult | null;
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
