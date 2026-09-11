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
| Retailers | Amazon / eBay / Flipkart / Daraz (need program credentials) | `SampleCatalogProvider` — 8 real, working products (`app/retailers/`) |

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
(20 tables: users, credits, photos, products, try-on jobs/results, outfits,
affiliate clicks, AI usage, subscriptions/payments, ...).

## Adding a real retailer

Implement `ProductProvider` in `app/retailers/<name>.py` (there are stub
adapters for Amazon/eBay/Flipkart/Daraz already sketched out — they raise
`RetailerNotConfiguredError` until their API credentials are set in
`.env`), register it in `app/retailers/registry.py`. The ingestion service
skips any retailer that isn't configured or fails, so partial credentials
never break the sync.

## Testing without real provider keys

Everything above defaults to its mock — the full user journey (register →
upload photos → browse products → try on → credits debited/refunded → shop
now → admin dashboard) works end to end against SQLite + in-process jobs +
local disk storage with no external accounts. Flip `VIRTUAL_TRYON_PROVIDER`,
`LLM_PROVIDER`, `PAYMENT_PROVIDER` to the real value once you have keys.
