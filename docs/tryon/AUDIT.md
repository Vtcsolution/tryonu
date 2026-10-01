# TryOnU Try-On Pipeline — Phase 1 Audit

Read-only. No behavior changed to produce this document. Every claim below is grounded in the current code (paths and line references as of this audit) or explicitly marked as unverified/estimated.

---

## 1. Stack map

**Backend** — `apps/api`: Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic migrations, Pydantic v2/pydantic-settings. Served by `uvicorn` (2 workers) in the Dockerfile; the live VPS deployment this session has worked against runs it via `pm2` (`tryonu-api`, `tryonu-worker`) directly on the host, not via `docker-compose` — the repo has Docker/Compose config (`apps/api/Dockerfile`, `docker-compose.yml`) that mirrors "production shape" for local dev, but I have not directly confirmed docker-compose is what actually runs in production; pm2 process names are the only production deploy mechanism I've used all session. **Flag as open question for Checkpoint 1.**

**Frontend** — `apps/web`: Next.js (App Router), TypeScript, React Query. Deployed as a Next.js "standalone" build; note from an earlier session: the standalone build's static assets must be copied into `.next/standalone/apps/web/.next/static`, not `.next/standalone` — a known footgun in this repo's deploy process.

**Database** — Postgres with the `pgvector` extension (`pgvector/pgvector:pg16` in docker-compose; production is Supabase Postgres per prior session notes). Local dev/tests fall back to SQLite (`aiosqlite`) — this SQLite+`StaticPool`+in-process-asyncio combination is the source of a known, pre-existing, load-dependent test flake unrelated to the try-on pipeline (documented and repeatedly isolated earlier this session via `git stash`/bisection, e.g. `test_best_of_survives_one_engine_failing_outright`).

**Queue/jobs** — Redis + RQ (`redis==5.2.1`, `rq==2.1.0`). `app/services/queue.py` is the single abstraction: `enqueue_tryon_job(job_id)` pushes to an RQ queue named `tryon` when `REDIS_URL` is set (production shape, pm2's `tryonu-worker` is an RQ worker process — `python -m app.workers.worker`); when `REDIS_URL` is unset (local dev without Redis running, and the test suite), it instead does `asyncio.create_task(run_tryon_job_async(job_id))` on the same event loop. **The worker task body (`run_tryon_job_async` in `app/workers/tasks/tryon_tasks.py`) is identical either way** — this is a clean, already-existing seam for Ground Rule 2's `TRYON_PIPELINE=legacy|hybrid` flag to plug into, and for Phase 3's run-state/resumability work.

**Storage** — `app/services/storage_service.py`: an `S3StorageBackend` (boto3, works against real S3 or any S3-compatible endpoint — MinIO locally, likely Cloudflare R2 or similar in production given the Dockerfile's comment) or a `LocalDiskStorageBackend`, selected automatically by whether S3 credentials are configured (`is_s3_configured()`). No code changes needed to add new artifact kinds (per-stage pipeline outputs) — `get_storage().put(key, bytes, content_type)` is the existing primitive.

**Image processing runtime today** — `opencv-python-headless` (CPU only) + `Pillow`, used for: basic decode/encode/resize/crop (`compose.py`), **Haar-cascade frontal face detection** (`face_restore.py:23`, `cv2.CascadeClassifier(... "haarcascade_frontalface_default.xml")` — a 2001-era classical detector, not a modern DNN), and colour/contrast matching (`compose.py`'s `match_colors`/`match_local_tone`). **There is no GPU runtime, no PyTorch/TensorFlow/ONNX, no pose estimator, no segmentation/parsing model, no depth model, and no embedding model for images anywhere in this codebase.** `requirements.txt` confirms this directly — no `torch`, `torchvision`, `onnxruntime`, `mediapipe`, `insightface`, `diffusers`, or similar. Every "understands the photo" capability today is an external paid API call (OpenAI vision/chat-completions, Gemini generateContent) wrapped in `app/services/tryon_quality/vision.py`'s `ask_json()`.

**Existing vector infra, partially reusable** — `pgvector` IS already wired up (`Product.embedding: Vector(1536)`, `app/services/search_service.py`), but it's a **text** embedding ("name brand category color description" → OpenAI text embedding, `app/ai/embeddings.py`) used for semantic catalog search, not an image embedding. The column type, index pattern (ivfflat/hnsw), and cosine-similarity helper are reusable scaffolding for Phase 2's "appearance match via embedding + distractor set" verification signal, but a genuinely new **image** embedding pipeline (e.g., CLIP/DINO) would still need to be built — nothing today embeds a product *photo*.

**Deployment implication for Phase 2's target architecture**: introducing any of IDM-VTON/CatVTON/OOTDiffusion-class models means standing up GPU infrastructure that does not exist today in any form — not an incremental addition to the current stack. This is the single largest scope/cost item in the whole brief and is flagged in detail in Checkpoint 1's open questions.

---

## 2. Request flow, end to end

```
apps/web/src/components/try/TryFlow.tsx
  → product selection: either
      (a) stylistApi.ask() → POST /api/v1/stylist/ask
          → app/api/v1/endpoints/stylist.py
          → app/services/stylist_service.py: ask_stylist()
              → live_search() per extracted item term (app/services/live_search_service.py)
                  → app/retailers/{ebay,aliexpress,cj,rakuten,amazon,flipkart,daraz,sample}.py
              → relevance.keep_relevant() filters/ranks real retailer results
              → OpenAI LLM call (get_stylist_provider().recommend(...)) picks indices
                  from the live candidate pool — never invents a product
              → persist_single_product() saves only the chosen ones as real DB rows
      (b) or the shopper picks straight from search/catalog (no stylist LLM)
  → outfit/product/wardrobe-item id(s) attached to the try-on request
  ↓
POST /api/v1/tryon  (app/api/v1/endpoints/tryon.py)
  → creates a TryOnJob row (status=queued), charges/reserves credits
  → queue.enqueue_tryon_job(job_id)  — see §1, RQ or in-process asyncio
  → HTTP response returns immediately with status="queued"
  ↓
app/workers/tasks/tryon_tasks.py: run_tryon_job_async(job_id)
  → builds a list[_Layer] from the job's product/outfit/wardrobe_item
      (render_plan() in app/services/outfit_slots.py resolves slot order,
       de-duplicates non-stackable slots like "top", keeps stackable
       jewellery)
  → picks ONE of four branches, in this priority order, based on the
    configured provider's capability flags + TRYON_QUALITY_PIPELINE:
      1. provider.supports_masked_edit  → render_masked_look()  (masked.py)
      2. provider.preserves_person      → render_whole_look()   (pipeline.py)
      3. else (quality pipeline on)     → render_look()         (pipeline.py)
      4. quality pipeline off           → provider.generate_outfit() directly,
                                           no verification of any kind
  → each of the three quality-pipeline branches returns
    (image_bytes, list[ItemReport]) — see §5 for what each does internally
  → _placements(layers, reports) turns per-item ItemReport into the
    API's per-product "drawn"/"reason"/"box" fields (as of today's fix,
    keyed on report.verified — see §5/§6)
  → _complete_job() stores the final image, marks the job completed
  ↓
GET /api/v1/tryon/{id}  (polled by the frontend)
  → TryOnJobOut includes result.placements and outfit.rendered_item_ids
  → apps/web renders "N of M items drawn on the photo" and per-item
    "on photo" / "matched" badges from these same fields
```

Credits/billing, auth, photo upload/storage, and the retailer integrations are all untouched by anything in today's or this audit's scope and are **not** part of the try-on core.

---

## 3. Every paid call site

| # | File : function | Provider | What's sent | Called how often per try-on request | Retry |
|---|---|---|---|---|---|
| 1 | `app/services/tryon_quality/product_prep.py` : `describe_product()` | OpenAI chat-completions (vision) | one product photo + its listing title | once per **distinct product image URL**, cached indefinitely in storage by URL hash — not once per run | none (falls back to the raw title on `VisionError`) |
| 2 | `app/services/tryon_quality/judge.py` : `judge()` | OpenAI chat-completions (vision) | product photo, a before/after crop of the item's own region, the whole after-photo | once per item per attempt (shared batch attempt + any individual retry), in every one of the three quality pipelines | none built in; the retry *is* the pipeline's own retry loop |
| 3 | `app/services/tryon_quality/judge.py` : `check_for_extra_items()` (added this session) | OpenAI chat-completions (vision) | whole before/after photo + the list of selected products' descriptions | once per `render_whole_look()` run (not per item) | fails open (returns `[]`) on `VisionError` |
| 4 | `app/services/tryon_quality/locate.py` : `find_body_part()` | OpenAI chat-completions (vision) | the photo + a body-part name | only for items whose placement needs a real lookup (ring/bracelet/watch/bag-class items whose name regex matches, when the free geometric fast path doesn't apply) | none |
| 5 | `app/ai/providers/openai_image.py` : `generate_outfit()` / `edit_masked()` | OpenAI image generation (`images/edits`) | the person photo + every product photo in the batch (≤`MAX_PIECES`=15 images total), or one product + one real API-level mask for the masked pipeline | masked pipeline: once per item per wave per attempt. Whole-outfit: once per batch (`ceil(products / 15)`) per shared attempt, plus one call per item that needs an individual retry | `tenacity`, 3 attempts, exponential backoff, only on retryable HTTP errors |
| 6 | `app/ai/providers/gemini_image.py` : `generate_outfit()` | Google Gemini `generateContent` (image) | same shape as #5 | same cadence as #5's whole-outfit case | `tenacity`, 3 attempts |
| 7 | `app/ai/providers/fashn.py` : `generate()` | FASHN (`/run` + poll `/status`) | one person photo URL + one product photo URL (FASHN fetches them itself) | once per item (FASHN has no whole-outfit mode) | `tenacity`, 4 attempts |
| 8 | `app/services/stylist_service.py` → `get_stylist_provider().recommend()` | OpenAI chat-completions (text) | the shopper's prompt + up to ~40-60 live-searched candidate products (text fields only, no images) | once per `ask_stylist()` call (i.e., once per "describe a look" search) | none |

**Cost per request — rough shape, not verified current USD prices** (OpenAI/Gemini pricing changes; I have not fetched current rates, so treat every number here as *relative*, not absolute):
- A typical N-selected-item whole-outfit (Gemini) request: `N` cached-or-fresh `describe_product` calls + 1 `check_for_extra_items` call + (`ceil(N/15)` batches × (1 + retries) judge-calls-per-item) + 1 image-generation call per batch per attempt + up to `N` individual-retry image-generation calls in the worst case (every item needing a solo retry).
- The masked pipeline (OpenAI) is the most expensive per item (one real image-edit API call per item, not batched) but the most reliable per item (a real alpha-mask guarantee).
- `describe_product`'s cache means repeat try-ons of the *same* product across different shoppers/jobs cost nothing extra for that call — a real, already-working cost control.

---

## 4. Product data

**Ingestion** — `app/services/live_search_service.py` : `live_search(query)` fans out to every registered `ProductProvider` in `app/retailers/registry.py` (`aliexpress`, `amazon`, `cj`, `daraz`, `ebay`, `flipkart`, `rakuten`, plus a `sample` fixture provider), each returning `RawProduct` — a provider-agnostic shape: `name, price_cents, product_url, images: list[str], brand, category_slug, subcategory, gender, color, sizes, description, rating, availability, style_tags, merchant_name`. Results are deduplicated, filtered by `relevance.keep_relevant()`, cached in-process for 180s (`_CACHE_TTL_SECONDS`), and only the ones a shopper actually picks are persisted via `persist_single_product()` into the real `Product` table.

**Images** — never re-hosted or re-encoded at ingestion time; `RawProduct.images[0]` is the retailer's own CDN URL, fetched fresh (via `httpx`) wherever a pipeline needs the bytes. Real examples pulled live during this session (not synthetic): eBay listing photos at `https://i.ebayimg.com/images/g/.../s-l1600.jpg` — up to 1600px on the long side, almost always a clean studio/catalog shot (white or neutral background), occasionally an on-model or ghost-mannequin photo. I have **not** queried the production database for a random sample of 10 records — the local `.env` points at the production Supabase instance and this session's standing rule is never to run anything against it beyond read-only app traffic I don't control; pulling a live sample would need either a sanctioned read-only query run by you, or local SQLite seed fixtures (`tests/seeds` pattern used throughout the test suite) as a stand-in. **Flagging as an open question** rather than guessing.

**Metadata available for `ProductSpec` derivation (Phase 2)**: `category_slug`/`subcategory` exist but are retailer-defined, inconsistent across providers, and — critically — for eBay's ad-hoc search path specifically, `category_slug` is hardcoded to the literal string `"search"` (not a real taxonomy value) rather than a genuine category (`app/retailers/ebay.py:144`). **This means `category_slug` cannot be trusted as a reliable category signal for live-searched products today** — it's only meaningful for CJ's/Rakuten's own pre-browsed category feeds. `gender`, `color`, `style_tags` are present but retailer-reported, not visually derived. None of this is a substitute for the visually-derived `ProductSpec` the target architecture calls for; today's pipeline derives everything it uses (placement, description) from the product **photo**, via `describe_product()`'s single vision call, same as Phase 2 proposes — just producing a free-text description today instead of a structured, schema-validated object.

---

## 5. Current verification — how it decides a product was applied, and why it could produce false positives

Three different pipelines exist (selected per §2), each with its own verification shape:

- **`render_masked_look()`** (`app/services/tryon_quality/masked.py`) — real OpenAI alpha-channel masked edits. Each item gets its own API-enforced transparent window; everything outside it is refused at the API level, not reconstructed after the fact. `judge()` grades the result against that exact region. **As of this session's fixes**, the paste between sequential rounds is feathered (not a hard rectangle), a garment is never batched with anything else, hand-item windows are size-capped, and an exception from the edit call itself gets the same retry budget a quality miss does. This is today's **strongest** guarantee — closest in spirit to the target architecture's "pixel-lock" rule, though it's API-enforced rather than a locally-computed feathered-mask recomposite.

- **`render_whole_look()`** (`pipeline.py`, used for engines like Gemini that claim to preserve the person on their own) — one whole-outfit generation call, trusted as the final answer; no local masking or compositing inside this function at all. **Until this session, this was the weakest link**: every item was judged against the *entire photo* regardless of size (a watch judged against a full-body frame has no real chance of being confirmed present or absent), and the "on photo" label came from a *separate*, independent, weaker vision call (`find_item()` — a plain "does this appear somewhere, yes/no + box") with **zero connection** to `judge()`'s actual pass/fail verdict. An item that failed every retry could still get a box from that independent lookup and be reported as "on photo." **This is exactly the false-positive mechanism the user's "every item is on the photo" bug report demonstrated**, and it is fixed as of this session (see §6) — but the underlying *engine* still has no real mask; it relies entirely on the model's own instruction-following plus a post-hoc verification gate, never a guaranteed pixel boundary. This is the component the brief's target architecture (RigidCompositeStrategy / GenerativeVTOStrategy with pixel-lock) is most directly aimed at replacing.

- **`render_look()`** (`pipeline.py`, used for FASHN and as the OpenAI fallback when masked editing isn't used) — the oldest, most complex pipeline: renders once (whole-look if the engine supports it, else one call per item), then uses change detection (`compose.py`: `find_changes`, `_mask_from`, colour/local-tone correction) to decide which pixels are "the product" and merges only those back onto the original full-resolution photo. This is the one existing piece of code that already does something structurally close to "compositing onto an immutable base" — but it derives its mask from a *diff* against an unconstrained regeneration, not from true segmentation/placement geometry, which is documented in this file's own comments as the source of several of the worst historical artifacts (a seam across a collarbone, hair replaced by background, a blouse spattered across a room).

**Verification scoring itself** (`judge.py`): one vision call returns `product_match` / `worn_correctly` / `realism` (0–10 each) plus free-text issues, graded against the real product reference photo — already a reasonable proxy for the brief's "appearance match" and "placement" signals, just without the brief's proposed negative-control distractor set, local feature matching, OCR, or face-identity collateral check. It is a **single VLM opinion**, asked a scored question rather than a strict forced-choice — closer to what Phase 2's design wants than a plain yes/no, but not as rigorous as the proposed multi-signal verification.

---

## 6. Failure analysis — reported symptom → specific code cause

| Reported symptom | Root cause found | Status |
|---|---|---|
| Selected products silently dropped past a count limit | `generate_outfit()` truncates to `MAX_PIECES=15` images per call; items beyond the 15th were never sent to the model at all, yet still judged as "wrong" | **Fixed this session** — `render_whole_look()` now batches into sequential groups of ≤15, each batch building on the last |
| One stubborn item forces a full outfit re-roll | `render_whole_look()`'s retry loop redrew the *entire* batch on any single item's failure | **Fixed** — failed items now get one individual, single-item retry on the current image instead |
| "Every item is on the photo" when items are visibly missing | `_placements()` decided "drawn" from `report.box is not None`; `box` was set independently of whether `judge()`'s verdict actually passed, in all three pipelines (`find_item()`'s independent weak lookup for the whole-look path; unconditional box assignment before the pass/fail check in the other two) | **Fixed** — new explicit `ItemReport.verified` field, set only at a genuine pass/near-miss, is now the sole source of the "drawn" flag; `find_item()` was removed entirely (now dead code with no callers) |
| Final image soft / not HD | The photo sent to the model was downscaled to `MODEL_SIDE=1024px` — a cap whose own justification ("the person's pixels are safe, the merge happens on the full photo") is true for `render_look()`'s diff-merge design but false for `render_whole_look()`, which has no merge step | **Fixed** — `render_whole_look()` now sends the photo at working resolution (capped at 2048px, same ceiling used elsewhere), not the smaller model-speed cap |
| Gemini invents jewelry/accessories nobody selected | The whole-outfit prompt never said the product list was a closed set; no check existed that could notice an *extra*, unrequested item (every check only asks "is THIS selected product there") | **Fixed** — prompt now states the list is closed/exact; one additional whole-photo check compares before/after against exactly what was selected and fails the render if anything extra appears |
| Products redesigned / colour or shape drift | `judge()`'s `product_match` score already exists to catch this and triggers a retry with the specific issue fed back as a correction — this mechanism is sound where it runs, but (a) it never ran against the *correct* region for `render_whole_look()` before this session's fix, and (b) it has no negative-control/distractor comparison, so a confidently-wrong answer from the VLM itself isn't caught | **Partially addressed** (region fix); the brief's proposed distractor-set/local-feature verification is **not implemented** — open scope item for Phase 2 |
| Anatomy breaks / identity drift | `render_whole_look()` and the one-shot path rely entirely on the model's own instruction-following for identity (`_CANVAS` prompt: "face, hair, skin, body... come out as they went in") plus a post-hoc `keep_person()` diff-merge that restores the face/background region from the original photo. There is **no real identity-similarity check** (e.g., face embedding comparison) anywhere in the codebase today | **Not fixed, not previously diagnosed this session** — a real gap matching the brief's "collateral checks" requirement |
| Title/keyword-based mis-placement (e.g., a sneaker literally named "...6 Rings..." satisfying a jewelry-category word match) | `_area_for()`/`_mask_region()`'s placement dispatch is **regex-on-product-name**, not visually derived — confirmed and explained to you earlier this session, explicitly **not fixed yet** per your own instruction ("Do NOT change the placement architecture before this test") | **Diagnosed, intentionally deferred** — this is precisely the class of problem `ProductSpec.anchor` (visually derived, not keyword-derived) in the brief's Phase 2 design is meant to eliminate structurally |
| Quality degrades with each regeneration | Confirmed structurally for any pipeline that feeds a previous generation's *output* back in as the next step's input (`render_whole_look()`'s sequential batches, `render_look()`'s whole-look-then-per-item chain) — every such hand-off is a re-encode/re-generate cycle, and JPEG/model re-generation is lossy each time. The masked pipeline's feathered-paste fix reduces *visible seams* from this but doesn't eliminate the underlying re-encoding loss | **Structural, not fully fixable** without exactly the brief's "immutable original base + compositing" principle — today, only the masked pipeline's single-pass-per-item design and `render_look()`'s diff-merge-onto-original partially avoid it |

---

## 7. Reusable assets — keep these

- Auth, credits/billing, photo upload/storage (`storage_service.py`), job creation/polling API, RQ/in-process queue abstraction (`queue.py`) — none of this needs to change for the try-on core rebuild.
- Retailer integrations (`app/retailers/*`, 8 providers) and `live_search_service.py` — product sourcing is solid and entirely separate from how a product gets visually applied.
- `relevance.py`'s department-aware keyword filtering — a real, tested, working piece of the *search* path (distinct from the try-on *placement* path, which is the thing under review here).
- The AI stylist (`stylist_service.py`) — picks real products from live candidates, never invents one; orthogonal to the try-on core.
- `product_prep.py`'s `describe_product()` **and its cache-by-image-hash pattern** — directly reusable as (or alongside) Phase 2's `ProductSpec` visual-analysis step; the caching discipline ("paid once per product image, never per run") is exactly Ground Rule/Phase-2 requirement already implemented once.
- `judge.py`'s scoring concept and prompt-engineering lessons (small-item leniency, region-cropped before/after) — a good starting point for Phase 2's VLM-based checks, even though the brief wants additional non-VLM signals alongside it.
- `masked.py`'s real API-level alpha-mask edit path — the existing component closest in spirit to "controlled inpainting," and the one pipeline with a genuine (API-enforced) pixel-boundary guarantee today.
- `compose.py`'s colour/local-tone matching and feathered-blend primitives (`composite()`, `match_colors`, `match_local_tone`) — directly reusable inside a new pixel-lock compositor; this is real, tested, working recomposite math already in the codebase.
- `pgvector` + the `Product.embedding` column/index pattern — infra reusable for an eventual image-embedding verification signal, though the embeddings themselves are text-only today.
- The test suite's mocking discipline (`fake_vision`-style fixtures monkeypatching every paid call site, `MockTryOnProvider`, offline-first test design) — this is already exactly the shape Phase 4 asks for; extending it to new provider interfaces is additive, not a new pattern.

## Try-on core to be replaced (per the brief's scope)

`app/services/tryon_quality/pipeline.py` (`render_whole_look`, `render_look`, and their shared helpers), `app/services/tryon_quality/masked.py`, the `_mask_region`/`_area_for`/`_plausible_area` placement dispatch, and the provider `generate_outfit()`/`edit_masked()` calls they drive. `judge.py` and `product_prep.py` are candidates for **extension**, not full replacement, per the reuse notes above.

---

## 8. Test baseline

- Framework: `pytest` + `pytest-asyncio`, 50 test files, **558 tests**, SQLite + `StaticPool` for the DB in tests (async, in-process job execution when `REDIS_URL` is unset — the normal test path).
- Current state: **558 passed** as of this audit, one known pre-existing, load-dependent flake (`test_best_of_survives_one_engine_failing_outright` — a polling-timeout race under heavy concurrent test load, confirmed via `git stash`/commit-bisection earlier this session to predate every change made this session; passes reliably in isolation or under normal load).
- Try-on path coverage: `tests/test_masked_tryon.py` (35 tests), `tests/test_tryon_quality.py` (~58 tests covering both `render_look` and `render_whole_look`), `tests/test_openai_tryon.py`, `tests/test_tryon.py` (worker/API integration level) — all fully offline, every paid call site monkeypatched via fixtures (`fake_vision` and similar), zero network access required. This is precisely the "mock-everything, deterministic, no paid calls" discipline Phase 4 asks for — it already exists for the current pipeline and is the direct template for the new one's mock providers.
- No GPU/CV-specific tests exist (nothing to test yet — no segmentation/pose/parsing code exists today).
- No dedicated "verification false-positive" adversarial test suite existed before this session; this session added the first examples of that exact pattern (an item that never passed is never reported as applied; an item nobody selected fails the whole render) — a direct precedent for Phase 4's adversarial verification tests (missing/wrong/duplicate/invented product cases).

---

## Checkpoint 1 — open questions (need your answer before Phase 2 can be meaningfully scoped)

1. **Production deploy mechanism**: is production actually running via `docker-compose` (making GPU-container addition a known, bounded change) or bare pm2 on a VPS (making it a from-scratch infra project — provisioning a GPU host, CUDA drivers, model-serving process, health checks, the works)? I've only ever used pm2 commands this session and have no confirmation either way.
2. **Appetite for new infrastructure cost**: every specialized VTO model worth evaluating (IDM-VTON, CatVTON, OOTDiffusion, and the actively-maintained field generally) needs a GPU at inference time — there is currently *zero* GPU infrastructure anywhere in this stack. This is a new, ongoing cost (either a rented GPU instance running continuously, or serverless-GPU cold-start latency on each request) layered on top of the existing OpenAI/Gemini/FASHN per-call costs, not a replacement for them. Given this session's repeated, explicit cost-sensitivity ("in just two tries my $1 has been deducted"), I want this traded off explicitly before Phase 2 recommends a specific provider/hosting shape.
3. **Scope of "arbitrary products"**: the specialized VTO models under evaluation (IDM-VTON/CatVTON/OOTDiffusion family) are trained specifically for **upper/lower-body garments** worn on a roughly frontal, standing person (VITON-HD/DressCode-style datasets). None of them natively handle rings, bracelets, watches, bags, sunglasses, or shoes — categories this platform already sells and tries on today. Phase 2's hybrid design (specialized VTO for `drape`-class garments, rigid-composite for everything else) is the only coherent way to reconcile "arbitrary products" with "use a specialized VTO model," and I want to confirm that's the direction before writing the full architecture doc, rather than have Phase 2 silently narrow what "arbitrary products" means.
4. **Real product-photo sample**: I don't have a safe way to pull 10 live production records (local `.env` targets the production DB, which this session's standing rules say never to query/write against beyond normal read-only app behavior). I can supply 10 *real* records fetched live via `live_search()` during this session (eBay results actually returned for real queries), which are genuine retailer data, just not a DB-table sample. Acceptable substitute, or do you want to run a read-only export yourself?
5. **License verification**: I have not yet researched current licensing for IDM-VTON/CatVTON/OOTDiffusion (and their dependency chains — some rely on SCHP/DensePose/OpenPose components with their own, sometimes research-only, licenses) — that's Phase 2 work per the brief's own structure. Flagging now so the Phase 2 checkpoint doesn't surprise you with `UNVERIFIED` entries.

No code has been changed. Waiting for approval to proceed to Phase 2.
