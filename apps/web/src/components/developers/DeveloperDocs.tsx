"use client";

import { useState } from "react";
import { API_BASE_URL } from "@/lib/api/client";

const API_ROOT = API_BASE_URL || "https://api.tryonu.app";
const BASE = `${API_ROOT}/api/v1/public`;
export const WIDGET_SRC = "https://tryonu.app/widget.js";
export const PLUGIN_ZIP = "/downloads/tryonu-try-on.zip";

/** The two lines a shop pastes into its website. */
export function widgetSnippet(key = "tou_pk_YOUR_WEBSITE_KEY") {
  const api = API_ROOT === "https://api.tryonu.app" ? "" : ` data-api="${API_ROOT}"`;
  return `<script src="${WIDGET_SRC}" data-key="${key}"${api} defer></script>
<button data-tryonu-garment="https://your-shop.com/product-photo.jpg" data-tryonu-name="Product name"></button>`;
}

export function shopifySnippet(key = "tou_pk_YOUR_WEBSITE_KEY") {
  const api = API_ROOT === "https://api.tryonu.app" ? "" : ` data-api="${API_ROOT}"`;
  return `<script src="${WIDGET_SRC}" data-key="${key}"${api} defer></script>
<button data-tryonu-garment="{{ product.featured_image | image_url: width: 1200 | prepend: 'https:' }}"
        data-tryonu-name="{{ product.title | escape }}"></button>`;
}

type Shop = "website" | "shopify" | "wordpress";
const SHOPS: { id: Shop; label: string }[] = [
  { id: "website", label: "Any website / Wix" },
  { id: "shopify", label: "Shopify" },
  { id: "wordpress", label: "WordPress / WooCommerce" },
];

type Lang = "curl" | "javascript" | "python" | "php" | "wordpress";

const LANGS: { id: Lang; label: string }[] = [
  { id: "curl", label: "cURL" },
  { id: "javascript", label: "JavaScript (Node)" },
  { id: "python", label: "Python" },
  { id: "php", label: "PHP" },
  { id: "wordpress", label: "WordPress / WooCommerce" },
];

const CODE: Record<Lang, string> = {
  curl: `# 1. Start a try-on (photos as files)
curl -X POST ${BASE}/tryons \\
  -H "Authorization: Bearer $TRYONU_API_KEY" \\
  -F person_image=@customer.jpg \\
  -F garment_image=@dress.jpg \\
  -F reference=order-123

# ...or as public links (JSON)
curl -X POST ${BASE}/tryons \\
  -H "Authorization: Bearer $TRYONU_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"person_image_url": "https://your-site.com/customer.jpg",
       "garment_image_url": "https://your-site.com/dress.jpg"}'

# 2. Ask until "status" is "completed" (about 20-60 seconds)
curl ${BASE}/tryons/TRYON_ID -H "Authorization: Bearer $TRYONU_API_KEY"

# Credits left
curl ${BASE}/credits -H "Authorization: Bearer $TRYONU_API_KEY"`,

  javascript: `// Node 18+ (built-in fetch). Run this on your SERVER, never in the browser.
const API = "${BASE}";
const headers = {
  Authorization: \`Bearer \${process.env.TRYONU_API_KEY}\`,
  "Content-Type": "application/json",
};

async function tryOn(personImageUrl, garmentImageUrl) {
  let job = await fetch(\`\${API}/tryons\`, {
    method: "POST",
    headers,
    body: JSON.stringify({ person_image_url: personImageUrl, garment_image_url: garmentImageUrl }),
  }).then((r) => r.json());

  while (job.status === "queued" || job.status === "processing") {
    await new Promise((r) => setTimeout(r, 3000));
    job = await fetch(\`\${API}/tryons/\${job.id}\`, { headers }).then((r) => r.json());
  }
  if (job.status !== "completed") throw new Error(job.error || job.detail || "Try-on failed");
  return job.result_image_url; // download and keep it: the link expires
}

tryOn("https://your-site.com/customer.jpg", "https://your-site.com/dress.jpg").then(console.log);`,

  python: `# pip install requests
import os, time, requests

API = "${BASE}"
HEADERS = {"Authorization": f"Bearer {os.environ['TRYONU_API_KEY']}"}

def try_on(person_path: str, garment_path: str) -> str:
    with open(person_path, "rb") as person, open(garment_path, "rb") as garment:
        job = requests.post(f"{API}/tryons", headers=HEADERS,
                            files={"person_image": person, "garment_image": garment},
                            data={"reference": "order-123"}, timeout=60).json()
    while job.get("status") in ("queued", "processing"):
        time.sleep(3)
        job = requests.get(f"{API}/tryons/{job['id']}", headers=HEADERS, timeout=30).json()
    if job.get("status") != "completed":
        raise RuntimeError(job.get("error") or job.get("detail") or "Try-on failed")
    return job["result_image_url"]  # download and keep it: the link expires

print(try_on("customer.jpg", "dress.jpg"))`,

  php: `<?php
// Any PHP site (PHP 7.4+ with cURL). Keep the key on your server.
$api = "${BASE}";
$key = getenv("TRYONU_API_KEY");

function tryonu($method, $url, $key, $body = null) {
    $ch = curl_init($url);
    $headers = ["Authorization: Bearer " . $key];
    if ($body !== null) {
        $headers[] = "Content-Type: application/json";
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($body));
    }
    curl_setopt_array($ch, [CURLOPT_CUSTOMREQUEST => $method, CURLOPT_HTTPHEADER => $headers,
                            CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 60]);
    $result = json_decode(curl_exec($ch), true);
    curl_close($ch);
    return $result;
}

$job = tryonu("POST", "$api/tryons", $key, [
    "person_image_url"  => "https://your-site.com/customer.jpg",
    "garment_image_url" => "https://your-site.com/dress.jpg",
    "reference"         => "order-123",
]);
while (in_array($job["status"] ?? "", ["queued", "processing"])) {
    sleep(3);
    $job = tryonu("GET", "$api/tryons/" . $job["id"], $key);
}
echo $job["result_image_url"] ?? ($job["error"] ?? $job["detail"]);`,

  wordpress: `<?php
// In your theme's functions.php or a small plugin.
// Add to wp-config.php:  define('TRYONU_API_KEY', 'tou_sk_...');
// No code needed? Install the TryOnU plugin instead (see "Add a Try it on button" above).

function tryonu_start($person_url, $product_id) {
    $garment_url = wp_get_attachment_url(get_post_thumbnail_id($product_id));
    $response = wp_remote_post('${BASE}/tryons', [
        'headers' => ['Authorization' => 'Bearer ' . TRYONU_API_KEY,
                      'Content-Type'  => 'application/json'],
        'body'    => wp_json_encode(['person_image_url'  => $person_url,
                                     'garment_image_url' => $garment_url,
                                     'garment_name'      => get_the_title($product_id),
                                     'reference'         => 'product-' . $product_id]),
        'timeout' => 60,
    ]);
    return json_decode(wp_remote_retrieve_body($response), true); // ['id' => ..., 'status' => ...]
}

function tryonu_result($tryon_id) {
    $response = wp_remote_get('${BASE}/tryons/' . $tryon_id, [
        'headers' => ['Authorization' => 'Bearer ' . TRYONU_API_KEY],
    ]);
    return json_decode(wp_remote_retrieve_body($response), true); // check 'status' and 'result_image_url'
}`,
};

const FIELDS: [string, string][] = [
  ["id", "The try-on's id. Use it to ask for the result."],
  ["status", "queued → processing → completed, or failed."],
  ["result_image_url", "The finished picture, once completed. Download and keep it: the link expires."],
  ["error", "Why it failed (a failed try-on gives the credit back)."],
  ["reference", "Your own reference, returned as you sent it."],
  ["credits_used", "1 per try-on, 0 if it failed."],
  ["credits_left", "Your balance, on the reply to a new try-on."],
];

const ERRORS: [string, string][] = [
  ["400", "A photo is missing, isn't an image, or its link isn't a public web address."],
  ["401", "No API key, a wrong key, or a revoked key."],
  ["402", "No credits left. Buy a pack in the developer portal."],
  ["403", "The developer account is suspended, or (website key) the page isn't on one of the key's domains."],
  ["404", "No try-on with that id on your account."],
  ["429", "Too many requests, or TryOnU's daily capacity is reached. Nothing was charged; try again later."],
];

/** How to use the TryOnU try-on API, with code for each platform. */
export function DeveloperDocs({ compact = false }: { compact?: boolean }) {
  const [lang, setLang] = useState<Lang>("curl");
  const [shop, setShop] = useState<Shop>("website");
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(CODE[lang]);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };
  const card = "rounded-[24px] border border-line bg-surface p-6";

  return (
    <div className="space-y-6">
      {!compact && (
        <section id="how-it-works" className={`${card} scroll-mt-24`}>
          <h2 className="font-display text-[24px] text-ink">How it works</h2>
          <ol className="mt-3 space-y-2 text-[15.5px] leading-relaxed text-ink-soft">
            <li><b className="text-ink">1.</b> Your server sends TryOnU a <b>photo of your customer</b> and a <b>photo of your product</b>.</li>
            <li><b className="text-ink">2.</b> TryOnU dresses the customer in the product with AI. It takes about 20–60 seconds.</li>
            <li><b className="text-ink">3.</b> You get back a <b>picture of your customer wearing it</b>, to show on your site or app.</li>
          </ol>
          <p className="mt-3 text-[14px] text-muted">
            Each try-on uses <b>1 credit</b>. A failed try-on gives the credit back. Credits never expire.
          </p>
        </section>
      )}

      <section id="widget" className={`${card} scroll-mt-24`}>
        <h2 className="font-display text-[22px] text-ink">Add a &quot;Try it on&quot; button to your shop</h2>
        <p className="mt-1 text-[15px] text-ink-soft">
          No coding. Shoppers press the button, add a photo and see themselves in your product. It uses a{" "}
          <b>website key</b> (<code>tou_pk_…</code>) that works only on your website.
        </p>
        <div role="tablist" aria-label="Shop platform" className="mt-4 flex flex-wrap gap-2">
          {SHOPS.map((p) => (
            <button
              key={p.id}
              type="button"
              role="tab"
              aria-selected={shop === p.id}
              onClick={() => setShop(p.id)}
              className={`min-h-[38px] rounded-full px-4 text-[14px] font-medium transition-colors ${
                shop === p.id ? "bg-ink text-surface" : "border border-line text-ink-soft hover:border-line-strong"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        <WidgetSteps shop={shop} />
      </section>

      <section id="code" className={`${card} scroll-mt-24`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-[22px] text-ink">Code for your platform (server API)</h2>
          <button
            type="button"
            onClick={copy}
            className="tu-press min-h-[38px] rounded-full border border-line-strong px-4 text-[14px] font-medium text-ink hover:border-ink/40"
          >
            {copied ? "Copied" : "Copy code"}
          </button>
        </div>
        <div role="tablist" aria-label="Language" className="mt-4 flex flex-wrap gap-2">
          {LANGS.map((l) => (
            <button
              key={l.id}
              type="button"
              role="tab"
              aria-selected={lang === l.id}
              onClick={() => setLang(l.id)}
              className={`min-h-[38px] rounded-full px-4 text-[14px] font-medium transition-colors ${
                lang === l.id ? "bg-ink text-surface" : "border border-line text-ink-soft hover:border-line-strong"
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
        <pre className="mt-4 max-h-[520px] overflow-auto rounded-[16px] bg-[#0f0f0d] p-4 text-[13px] leading-relaxed text-[#e9e6dc]">
          <code>{CODE[lang]}</code>
        </pre>
        <p className="mt-3 text-[13.5px] text-[#a4553f]">
          Keep your secret key (<code>tou_sk_…</code>) on your server. Never put it in a web page or an app.
        </p>
      </section>

      <section id="reference" className={`${card} scroll-mt-24`}>
        <h2 className="font-display text-[22px] text-ink">Reference</h2>
        <div className="mt-3 space-y-2 text-[14.5px] text-ink-soft">
          <p><b className="text-ink">Base address:</b> <code>{BASE}</code></p>
          <p><b className="text-ink">Key:</b> header <code>Authorization: Bearer tou_sk_…</code> (or <code>X-API-Key: tou_sk_…</code>)</p>
          <ul className="mt-2 space-y-1">
            <li><code>POST /tryons</code> — start a try-on. Files <code>person_image</code> + <code>garment_image</code>, or JSON <code>person_image_url</code> + <code>garment_image_url</code>. Optional: <code>garment_name</code>, <code>reference</code>.</li>
            <li><code>GET /tryons/&#123;id&#125;</code> — the try-on&apos;s status and result.</li>
            <li><code>GET /credits</code> — credits left.</li>
            <li>
              Website widget (browser, website key in <code>X-TryOnU-Key</code>, only from the key&apos;s domains):{" "}
              <code>POST /widget/tryons</code> and <code>GET /widget/tryons/&#123;id&#125;</code>. Each visitor can make a few
              try-ons an hour.
            </li>
          </ul>
          <p className="pt-1 text-[13.5px] text-muted">
            Best photos: the customer standing, facing the camera, well lit; the product alone on a plain background. JPEG or PNG, up to 15 MB.
          </p>
        </div>
        <div className="mt-5 grid gap-5 md:grid-cols-2">
          <div id="responses" className="scroll-mt-24">
            <p className="text-[14px] font-semibold text-ink">What a try-on returns</p>
            <dl className="mt-2 divide-y divide-line rounded-[14px] border border-line text-[13.5px]">
              {FIELDS.map(([name, text]) => (
                <div key={name} className="flex gap-3 px-3 py-2">
                  <dt className="w-36 shrink-0 font-mono text-ink">{name}</dt>
                  <dd className="text-ink-soft">{text}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div id="errors" className="scroll-mt-24">
            <p className="text-[14px] font-semibold text-ink">Errors</p>
            <dl className="mt-2 divide-y divide-line rounded-[14px] border border-line text-[13.5px]">
              {ERRORS.map(([code, text]) => (
                <div key={code} className="flex gap-3 px-3 py-2">
                  <dt className="w-12 shrink-0 font-mono font-semibold text-ink">{code}</dt>
                  <dd className="text-ink-soft">{text}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </section>
    </div>
  );
}

/** Step-by-step: putting the widget on a shop, per platform. */
export function WidgetSteps({ shop, websiteKey }: { shop: Shop; websiteKey?: string }) {
  const step = "flex gap-3";
  const num = "grid h-7 w-7 shrink-0 place-items-center rounded-full bg-sage text-[13px] font-semibold text-white";
  const keyStep = (
    <li className={step}>
      <span className={num}>1</span>
      <span>
        In this portal, open <b>API keys</b> and create a <b>Website key</b> with your shop&apos;s address (for example{" "}
        <code>yourshop.com</code>). Buy credits: 1 credit = 1 try-on.
      </span>
    </li>
  );
  if (shop === "wordpress") {
    return (
      <ol className="mt-4 space-y-3 text-[15px] leading-relaxed text-ink-soft">
        {keyStep}
        <li className={step}>
          <span className={num}>2</span>
          <span>
            <a href={PLUGIN_ZIP} download className="font-semibold text-sage-deep underline">Download the TryOnU plugin</a>. In
            WordPress: <b>Plugins → Add New → Upload Plugin</b>, choose the file, <b>Install</b>, <b>Activate</b>.
          </span>
        </li>
        <li className={step}>
          <span className={num}>3</span>
          <span>
            <b>Settings → TryOnU Try-On</b>: paste your website key and save. The button appears under &quot;Add to cart&quot; on
            every product. (Or place it anywhere with <code>[tryonu_button]</code>.)
          </span>
        </li>
      </ol>
    );
  }
  const code = shop === "shopify" ? shopifySnippet(websiteKey) : widgetSnippet(websiteKey);
  return (
    <>
      <ol className="mt-4 space-y-3 text-[15px] leading-relaxed text-ink-soft">
        {keyStep}
        {shop === "shopify" ? (
          <li className={step}>
            <span className={num}>2</span>
            <span>
              In Shopify: <b>Online Store → Themes → Customize</b>, open a <b>product page</b>, <b>Add block → Custom Liquid</b>,
              paste the code below and <b>Save</b>. It uses each product&apos;s own main photo.
            </span>
          </li>
        ) : (
          <li className={step}>
            <span className={num}>2</span>
            <span>
              Paste the code below into your product page (on Wix: <b>Add → Embed code → Custom code</b>). Leave{" "}
              <code>data-tryonu-garment</code> empty to use the page&apos;s main picture.
            </span>
          </li>
        )}
      </ol>
      <CopyBlock code={code} />
    </>
  );
}

function CopyBlock({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="relative mt-4">
      <pre className="overflow-auto rounded-[16px] bg-[#0f0f0d] p-4 pr-24 text-[13px] leading-relaxed text-[#e9e6dc]">
        <code>{code}</code>
      </pre>
      <button
        type="button"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(code);
            setCopied(true);
            setTimeout(() => setCopied(false), 1800);
          } catch {
            setCopied(false);
          }
        }}
        className="tu-press absolute right-3 top-3 min-h-[34px] rounded-full bg-surface px-3 text-[13px] font-semibold text-ink"
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}
