# TryOnU API

FastAPI backend for TryOnU — auth, credits, the AI job pipeline, product
catalog + search, the AI stylist, and affiliate tracking.

Every external dependency (Postgres, Redis, S3/R2, the FASHN/OpenAI/Stripe
APIs, each retailer) sits behind an abstraction with a working mock/local
fallback, so the whole system runs and is testable with **zero external
services**:

| Concern | Production | Local fallback (no config needed) |
|---|---|---|
| Database | PostgreSQL + pgvector | SQLite file (`app/db/session.py`, `app/db/types.py`) |
| Job queue | Redis + RQ workers | in-process `asyncio.create_task` (`app/services/queue.py`) |
| Object storage | S3 / Cloudflare R2, private + presigned | local disk, HMAC-signed `/media` route (`app/services/storage_service.py`) |
| Virtual try-on | FASHN (`tryon-v1.6` / `tryon-max`) | `MockTryOnProvider` — real job lifecycle, stamped product image (`app/ai/providers/`) |
| Fashion stylist | OpenAI-compatible chat model | heuristic mock, same real-products-only contract (`app/ai/llm/`) |
| Payments | Stripe | instant-success mock (`app/payments/`) |
| Retailers | eBay Browse API and CJ Affiliate's GraphQL Product API — both **live-verified** with real production credentials, real inventory flowing (eBay: 200 real products synced; CJ: auth verified, blocked only on the account's own Product Feed API entitlement). Rakuten Advertising is architecturally complete and fully tested against mocks but **not yet live-verified** — no credentials exist yet (see `app/retailers/rakuten.py`'s module docstring). Amazon / Flipkart / Daraz still need program credentials | `SampleCatalogProvider` — 8 real, working products (`app/retailers/`) |
| Affiliate networks | Awin / CJ / Impact (Awin application submitted, awaiting approval — no real credentials exist yet) | `DirectAffiliateProvider` — plain `?ref=tryonu` links, always active (`app/affiliate_networks/`) |
| Email | SMTP | `MockEmailProvider` — logs the message instead of sending (`app/email/`) |

Swapping any of these is a config change (`.env`) — application code never
branches on "are we in prod."

## Run locally (no Docker)

```bash
cd apps/api
python -m venv .venv && .venv/Scripts/activate   # .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env    # or use the SQLite/mock defaults already in .env

alembic upgrade head
python -m app.scripts.seed --admin-email you@example.com --admin-password changeme
python -m app.scripts.ingest_products

uvicorn app.main:app --reload --port 8000
```

Docs at http://localhost:8000/docs. Health check at `/health`.

## Run with Docker (full stack: Postgres + Redis + MinIO + API + 2 workers + web)

```bash
docker compose up --build
```

Then, once, inside the `api` container (or via `docker compose exec api ...`):

```bash
docker compose exec api python -m app.scripts.seed --admin-email you@example.com --admin-password changeme
docker compose exec api python -m app.scripts.ingest_products
```

## Architecture

```
Next.js  --HTTP-->  FastAPI  --enqueue-->  Redis/RQ  --pull-->  Worker(s)
                       |                                           |
                       |<---------------- Postgres ---------------->|
                       |<---------------- S3 / R2 ------------------>|
```

- **AI jobs never run inside a request.** `POST /api/v1/tryon` debits
  credits, writes a `queued` job row, enqueues it, and returns — the worker
  (`app/workers/tasks/tryon_tasks.py`) does the actual generation and moves
  the job through `processing -> completed | failed`, refunding credits
  automatically on failure (with retry-then-refund for transient provider
  errors).
- **Credits are a ledger**, not just a counter — every grant/debit/refund is
  an append-only `CreditTransaction` row; `User.credits_balance` is a cache
  kept in sync in the same DB transaction (`app/services/credit_service.py`).
- **Providers are pluggable.** `app/ai/providers/`, `app/ai/llm/`,
  `app/retailers/`, `app/payments/` each define an abstract base + a
  registry that picks an implementation from config — add a new AI model,
  retailer, or payment processor without touching the API layer.
- **The AI stylist and search never invent products** — the LLM is shown a
  numbered shortlist of real DB rows and can only pick by index; results are
  mapped back to real `Product` records before being returned.

See `app/models/enums.py` and `app/models/__init__.py` for the full schema
(22 tables: users, refresh/password-reset tokens, credits, photos, products,
retailers/affiliate networks, try-on jobs/results, outfits, affiliate
clicks, AI usage, subscriptions/payments, ...).

## API surface

Routes are grouped under `/api/v1`: `auth` (register/login/refresh/logout,
Google OAuth, forgot/reset-password, email verification), `users`,
`photos`, `wardrobe` (user-owned items, distinct from the retailer
catalog), `products`, `search` (alias over the same catalog engine as
`products`), `tryon`, `stylist` (`/ask` is canonical; `/chat`,
`/recommend`, `/outfit` are the same engine, plus `/similar/{id}` and
`/cheaper/{id}` — deterministic catalog queries, no LLM call), `outfits`
(includes `/preview-compatibility`), `credits`, `subscriptions`,
`webhooks` (Stripe + a best-effort Rakuten postback listener), and `admin`
(overview, users, tryon-jobs, ai-usage, affiliate-clicks, retailers,
payments, subscriptions, plus `admin/rakuten/*` — status/search-preview/
advertisers/partnerships/offers/coupons — all role-gated, not just hidden
from the frontend). Full interactive list at `/docs`.

## Adding a real retailer

Implement `ProductProvider` in `app/retailers/<name>.py` (there are stub
adapters for Amazon/eBay/Flipkart/Daraz already sketched out — they raise
`RetailerNotConfiguredError` until their API credentials are set in
`.env`), register it in `app/retailers/registry.py`. The ingestion service
skips any retailer that isn't configured or fails, so partial credentials
never break the sync.

## Rakuten Advertising

Architecturally complete, fully tested against mocks, **not yet live-verified** (no credentials exist yet). See `app/retailers/rakuten.py`'s module docstring for the full verification-status caveat — every endpoint path and response field is a best-effort mapping from Rakuten's publicly documented API conventions, the same starting point eBay and CJ began from before their live-correction passes.

Covers: Product Search (catalog ingestion, disabled by default via `RAKUTEN_ENABLED=false`), Advertisers API v2, Partnerships API, Offers API, and Coupon API (all four as live admin-only pass-throughs under `/api/v1/admin/rakuten/*` — not persisted to new tables until a real response confirms the shape worth persisting), plus a best-effort Postback endpoint (`/api/v1/webhooks/rakuten`) that logs conversion callbacks for now rather than guessing at a persisted schema.

**To activate once you have real credentials:**
1. Set `RAKUTEN_ENABLED=true` plus either `RAKUTEN_CLIENT_ID`+`RAKUTEN_CLIENT_SECRET` (OAuth2 client_credentials) or a directly-issued `RAKUTEN_TOKEN` (+`RAKUTEN_REFRESH_TOKEN`) — whichever your account setup issues — and `RAKUTEN_PUBLISHER_ID`.
2. Hit `GET /api/v1/admin/rakuten/status` (admin-only) to confirm configuration is detected.
3. Hit `GET /api/v1/admin/rakuten/search?keyword=dress` to see a live, unsaved preview before running a full sync.
4. Run `python -m app.scripts.ingest_products` for the real catalog sync.
5. Expect at least one live-correction pass on exact field names/paths — flag whatever Rakuten's real response actually looks like and it's a fast, contained fix (the normalization logic lives in one place, `RakutenProductProvider._to_raw_product`).

## Supabase: keep the public API shut

Supabase hosts our Postgres, but it also puts a REST API in front of every
table in `public`, reachable by anyone with the project URL and the anon key.
Nothing here uses it — the API and worker connect straight to Postgres as
`postgres` — so it stays closed: RLS on with no policies, and the anon and
authenticated roles hold no grants. Postgres doesn't apply RLS to a table's
owner, so the app is unaffected.

`alembic upgrade head` applies it (migration `f1c8e42a7b03`). To do it by
hand, or to re-check after adding tables, paste
[scripts/supabase_lockdown.sql](scripts/supabase_lockdown.sql) into the
Supabase SQL editor — it's idempotent and ends with two queries that should
both return nothing.

## Testing without real provider keys

Everything above defaults to its mock — the full user journey (register →
upload photos → browse products → try on → credits debited/refunded → shop
now → admin dashboard) works end to end against SQLite + in-process jobs +
local disk storage with no external accounts. Flip `VIRTUAL_TRYON_PROVIDER`,
`LLM_PROVIDER`, `PAYMENT_PROVIDER` to the real value once you have keys.

## Automated tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

The suite (`apps/api/tests/`) runs against an isolated SQLite file with
every provider forced to its mock — no real API credits are ever spent by
`pytest`. It covers: registration/login/session auth, the credit ledger
(debit, insufficient-credits, idempotent debit-by-reference, refund,
double-refund guard), product/search catalog correctness, forgot/reset
password (including single-use-token and old-sessions-revoked behavior),
the full try-on job lifecycle (success debits credits, provider failure
fully refunds them), affiliate click tracking, the AI stylist's
real-products-only guarantee (including a hostile provider double that
returns out-of-range indexes, to prove they're dropped not fabricated),
admin-route authorization, Stripe webhook signature verification
(valid/tampered/wrong-secret/stale-timestamp/missing-header), the real
request/response shapes locked in from live eBay/CJ verification, and the
Rakuten integration's auth/throttling/error-handling/normalization
against the contract it defines (disabled state, missing credentials,
token refresh on a real 401, rate-limit/malformed-response/server-error
handling, dedup, and zero credential leakage in any response).
