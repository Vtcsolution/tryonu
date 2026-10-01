# Step 3 (Render) — Diagnosis of Bug A (identity breaks) and Bug B (5+ items fail)

Read-only. No behavior changed. Every finding below is grounded in the current code (file:line) or, where noted, external documentation — never assumed. No paid API calls were made; the one model-ID question that needed outside verification was checked against public provider documentation (a web search), not a call to our own integration.

---

## Hypothesis 1 — One-shot generation with too many references overloads the model

**CONFIRMED, and already partially mitigated this session, not yet to the degree this brief wants.**

`render_whole_look()` (`app/services/tryon_quality/pipeline.py`) sends every selected product in as few calls as possible. Earlier this session this was literally **one call for the whole outfit**, batched only enough to respect the API's hard image-count ceiling (`MAX_PIECES=15` in `app/ai/providers/openai_image.py:25`, shared by both OpenAI and Gemini adapters) — i.e. up to 15 products in a single generation call. That batching fix (commit `dfde86c`) stopped the specific failure of items past the 15th being silently dropped, but it did **not** address this brief's sharper claim: that even well under 15, small items (earrings, bangles, a watch) get overwhelmed or dropped when crammed alongside garments in one reference set. There is currently **no zone-based grouping** anywhere in the code — a "pass" today is just "up to 15 items, whatever they are, together." This brief's Stage 3 plan (max 2–3 garments per call, max 2–3 accessories per zone-call) is a real, structural tightening beyond what exists, not a restatement of something already fixed.

---

## Hypothesis 2 — Aspect-ratio / resolution mismatch causing "broken into pieces"

**PARTIALLY CONFIRMED — the specific mechanism is real, but not exactly as stated; here is the precise chain.**

- Gemini's adapter (`app/ai/providers/gemini_image.py:172-175`) **does** set `imageConfig.aspectRatio`, chosen by `_aspect_ratio()` (lines 66-80) from the input photo's own ratio — but only to one of **three fixed buckets**: `{"portrait": "3:4", "landscape": "4:3", "square": "1:1"}`. A real phone photo's actual ratio (e.g. a full-body shot at 9:16 ≈ 0.56) snaps to the nearest bucket ("3:4" ≈ 0.75) — a genuine, confirmable mismatch for anything other than a roughly-4:3/3:4 photo, not corrected anywhere.
- A genuine `_NO_IMAGE_CONFIG` fallback exists (`gemini_image.py:45,171-181`): if the configured model rejects the `imageConfig` parameter with an HTTP 400, the code retries **without any aspect ratio at all**, falls back to Gemini's own default, and remembers this **per-process** (an in-memory set) for every subsequent call. I cannot confirm from code alone whether this has ever actually triggered in production for the currently configured model — **the fastest way to check this for free is to grep the VPS's own logs for `gemini_image_no_image_config`**, which I don't have access to without you running it.
- Verified independently today via a real, successful live call (not reused from memory): a 459×668 (ratio 0.687) input photo produced a 1792×2400 (ratio 0.747) output — consistent with the "3:4" (0.75) bucket being applied correctly for *that* input, not a square/default fallback. So for a roughly-portrait photo close to 3:4, this mechanism is working. The risk is specifically for photos further from the three buckets.
- **The compositing side confirms the "broken into pieces" mechanism directly.** `keep_person()` (`pipeline.py:908-923`, the step that runs *after* `render_whole_look()` in the real job path and which my own earlier live test this session never exercised) calls `find_changes(base, decode(render_bytes), protect)`, which calls `align(render, base)` (`compose.py:67-102`). `align()`'s **first** operation is `cv2.resize(render, (w, h), ...)` — a direct resize to the base photo's exact pixel dimensions with **no aspect-ratio preservation**. If the render's aspect ratio differs meaningfully from the base's (exactly the scenario above, for any photo not close to 3:4/4:3/1:1), this resize **stretches the person non-uniformly** before the subsequent ORB feature-matching ever runs. The function does have a sanity check afterward (`if not 0.9 < scale < 1.1 or shift > 0.08 * max(w,h): return resized, 0.0`) that detects when the *subsequent affine fit* is implausible, but that check runs on an already-stretched image, and falling back to "just the stretched resize, no alignment" (confidence 0.0) is itself a visibly distorted result being merged in `find_changes()`'s diff — a very plausible source of "broken into pieces."

**My own earlier "it worked" live test this session did not actually test this failure path, because it called `render_whole_look()` directly and never ran the `keep_person()` step that follows it in the real job pipeline.** That's a real gap in my own earlier verification, flagged honestly.

---

## Hypothesis 3 — EXIF orientation not applied

**CONFIRMED — and worse than stated: the orientation data is actively discarded, not just unapplied.**

`app/services/image_service.py:validate_and_optimize()` — the function that processes every uploaded photo before storage — opens the image with PIL, verifies it, converts mode, calls `img.thumbnail(...)`, and re-saves as a fresh JPEG. At no point does it call `ImageOps.exif_transpose()` or read `img.getexif()`'s orientation tag. The function's own docstring states the intent plainly: *"this both strips EXIF/GPS metadata and neutralises polyglot-file attacks"* (`image_service.py:3-6`) — it deliberately rebuilds the image from decoded pixels, discarding EXIF, **without ever applying the rotation that tag would have specified first**.

Consequence: a photo from a device that stores portrait photos as landscape pixels + a rotation tag (the normal behavior for the large majority of phone cameras, iPhones included) is saved to permanent storage sideways or upside-down, with the one piece of metadata that could have corrected it already gone. Every downstream step — `cv2.imdecode` (which also ignores EXIF, confirmed at `compose.py:53-54`), the Haar-cascade face detector, every try-on pipeline — then operates on an incorrectly-oriented photo as if it were the real one. This is not a rare edge case; it is the default behavior for a large share of real phone uploads, and it is permanent once stored (the EXIF tag that could fix it later is gone).

---

## Hypothesis 4 — Model IDs

**Gemini: not confirmed as wrong, with a caveat. OpenAI: confirmed correct and current.**

- `GEMINI_IMAGE_MODEL` defaults to `gemini-3-pro-image` (`app/core/config.py:125`). A web search today returned mixed signal: some current documentation describes `gemini-3-pro-image-preview` as the generally-available image endpoint and lists `gemini-3-pro-image` as a GA id with an unclear/pending release status. **However, my own live call today, using exactly this configured id, succeeded and returned a real, correctly-sized image** — direct empirical evidence outweighs an ambiguous secondary source here. I am not reporting this as a confirmed bug, but it is worth setting explicitly to whichever id you've verified is stable for your account/quota, since provider aliasing behavior like this can change without notice. **I have not verified what the VPS's actual deployed `.env` currently sets this to** — same open question from earlier in this session, still unanswered.
- `OPENAI_IMAGE_MODEL` defaults to `gpt-image-2.5-sunburst` (`config.py:138`) — confirmed via web search to be a real, current OpenAI model (the "detailed/slower" variant of GPT Image 2.5, as opposed to "Flare," the faster one — released Sept 2026). This is correctly a dedicated **image** model, separate from `OPENAI_MODEL` (`gpt-4o-mini`, used only for the text-based stylist recommendation) and `OPENAI_VISION_MODEL` (`gpt-5.4-mini`, used only for the judge/describe/locate vision calls). **I found no code path anywhere that uses the text model (`OPENAI_MODEL`) for image generation** — the three settings are structurally separate in every call site I traced. The brief's example value ("gpt-5.6-sol") doesn't match anything in this codebase's defaults or any call site; if your production `.env` genuinely has something like that in `OPENAI_IMAGE_MODEL`, that would be a .env misconfiguration, not a code bug — and again, I can't check the actual deployed `.env` from here.
- The web search also confirmed, usefully, that `gpt-image-2.5-sunburst` genuinely supports **arbitrary `WIDTHxHEIGHT` resolution strings**, which is exactly what `_best_size()` (`openai_image.py`) already requests (matched to the photo's own aspect bucket, same three-bucket limitation as Gemini's — see Hypothesis 2). So OpenAI's path has the same coarse aspect-bucketing limitation as Gemini's, just not the "falls back to no config at all" failure mode.

---

## Hypothesis 5 — Messy / collage product reference images

**CONFIRMED as a real, live, previously-encountered problem — and important prior art exists in this exact codebase that the proposed fix needs to account for.**

There is currently no cropping, background removal, or variant-selection step anywhere in the product pipeline — `describe_product()` (`app/services/tryon_quality/product_prep.py`) only produces a **text** description; the retailer's raw listing photo, whatever it shows, is sent to the generation API exactly as-is, every time. Its own docstring (`product_prep.py:1-11`) documents a **specific prior incident with the exact failure mode this brief describes**, and — critically — that **the brief's proposed fix was already tried once and reverted**:

> *"The product IMAGE is never altered: the try-on model always gets the listing's main photo... Tested on real eBay listings, letting a vision model pick a 'cleaner' photo or crop to the product was worse than useless — it picked a white colour variant of a black shirt, cut a watch in half and cropped chinos to one leg, i.e. it swapped or damaged the product."*

This doesn't mean Stage 1's VLM-bounding-box-then-crop approach is wrong in principle — it means the **naive** version of it has already failed here, concretely, three distinct ways (wrong variant selected, product physically cut in half, product cropped to an unusable partial view). Any re-attempt needs a materially more careful design than "ask a VLM for a box and crop to it" — e.g., a high-confidence threshold with a hard fallback to the uncropped original, and validation that the box doesn't bisect the detected product. This is exactly the kind of thing Phase 2's design doc needs to address explicitly rather than re-walk into the same failure, and I'm flagging it now rather than silently.

---

## Hypothesis 6 — Whole-image regeneration on each step/retry compounds drift

**CONFIRMED — already documented in this session's broader architecture audit (`docs/tryon/AUDIT.md`, §6).** Any pipeline step that feeds a *previous generation's output* back in as the next step's base (`render_whole_look()`'s sequential batches, `render_look()`'s whole-look-then-per-item chain) re-encodes and regenerates on every hop; each hop is lossy. The masked pipeline's feathered-paste fix (this session) reduces *visible seams* from this but doesn't eliminate the underlying compounding loss — only an architecture where the **original photo stays the single immutable base for every step's compositing** (this brief's own Stage 4/5 pixel-lock design) removes it structurally.

---

## Summary table

| # | Hypothesis | Status | Where |
|---|---|---|---|
| 1 | One-shot, too many references | Confirmed; session's batching fix narrows but doesn't solve it | `pipeline.py` (`render_whole_look`) |
| 2 | Aspect-ratio / resolution mismatch | Confirmed mechanism (3-bucket snapping + non-aspect-preserving resize in `align()`); not confirmed as "defaults to square" for a portrait input | `gemini_image.py`, `compose.py:align()` |
| 3 | EXIF orientation | Confirmed, and worse than stated — EXIF is stripped without ever being applied, at upload time, permanently | `image_service.py:validate_and_optimize()` |
| 4 | Model IDs | OpenAI confirmed correct/current; Gemini unconfirmed as wrong (own live test succeeded) — VPS `.env` actual values still unverified | `config.py` |
| 5 | Messy/collage product images | Confirmed, with critical prior art: the proposed fix class was already tried and reverted here once | `product_prep.py` |
| 6 | Compounding regeneration drift | Confirmed, already documented in the broader audit | `pipeline.py`, `AUDIT.md` |

## What I have not yet done (correctly, per the ground rules)

No code changed. No paid call made. The Gemini/OpenAI model-name question was checked against public documentation only, never against our own integration.

## Open items before Phase 2 design can be fully grounded

1. VPS `.env`'s actual `GEMINI_IMAGE_MODEL` / `OPENAI_IMAGE_MODEL` values — still unconfirmed after being asked for several times this session.
2. VPS log check (free, no paid call) for `gemini_image_no_image_config` — would directly confirm or rule out whether the aspect-ratio fallback is actually firing in production.
3. Hypothesis 5's prior-art failure needs an explicit design answer in Phase 2, not a silent re-attempt.

Waiting for your approval before Phase 2 (implementation design).
