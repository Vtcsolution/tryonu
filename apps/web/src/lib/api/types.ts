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
