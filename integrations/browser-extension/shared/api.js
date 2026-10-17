// TryOnU browser extensions: talking to the TryOnU API with this browser's token.

export const SITE = "https://tryonu.app";
export const API = "https://api.tryonu.app/api/v1";

export async function getToken() {
  const { tryonuToken } = await chrome.storage.local.get("tryonuToken");
  return tryonuToken || null;
}

export async function setToken(token) {
  if (token) await chrome.storage.local.set({ tryonuToken: token });
  else await chrome.storage.local.remove("tryonuToken");
}

/** Calls the API; throws an Error whose message is safe to show the person. */
export async function api(path, { method = "GET", body } = {}) {
  const token = await getToken();
  if (!token) throw Object.assign(new Error("Connect TryOnU first."), { status: 401 });
  let res;
  try {
    res = await fetch(`${API}${path}`, {
      method,
      headers: { Authorization: `Bearer ${token}`, ...(body ? { "Content-Type": "application/json" } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Can't reach TryOnU. Check your internet connection.");
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401) await setToken(null);
    const detail = typeof data.detail === "string" ? data.detail : "Something went wrong. Please try again.";
    throw Object.assign(new Error(detail), { status: res.status });
  }
  return data;
}

export function openTryOnU(path) {
  return chrome.tabs.create({ url: `${SITE}${path}` });
}

/** Reads the product on the open tab (runs inside the page). */
export async function readProduct(tabId) {
  const [result] = await chrome.scripting.executeScript({ target: { tabId }, func: extractProduct });
  return result?.result || null;
}

// Runs inside the shop's page: must not use anything from outside this function.
export function extractProduct() {
  const abs = (u) => {
    try {
      return u ? new URL(u, location.href).href : "";
    } catch {
      return "";
    }
  };
  const num = (v) => {
    if (v == null) return null;
    const n = parseFloat(String(v).replace(/[^0-9.,]/g, "").replace(/,(?=\d{3}\b)/g, "").replace(",", "."));
    return Number.isFinite(n) && n > 0 ? n : null;
  };
  const out = { url: location.href, name: "", images: [], price: null, currency: null, description: "" };

  // 1. the page's own product data (schema.org), which most shops publish
  const products = [];
  const collect = (j) => {
    if (!j || typeof j !== "object") return;
    if (Array.isArray(j)) return j.forEach(collect);
    if (j["@graph"]) collect(j["@graph"]);
    const t = j["@type"];
    if (t === "Product" || (Array.isArray(t) && t.includes("Product"))) products.push(j);
  };
  document.querySelectorAll('script[type="application/ld+json"]').forEach((s) => {
    try {
      collect(JSON.parse(s.textContent));
    } catch {
      /* not JSON */
    }
  });
  const p = products[0];
  if (p) {
    out.name = String(p.name || "").trim();
    out.description = String(p.description || "").trim().slice(0, 1000);
    const imgs = Array.isArray(p.image) ? p.image : p.image ? [p.image] : [];
    imgs.forEach((i) => out.images.push(abs(typeof i === "string" ? i : i.url || i.contentUrl)));
    const offers = Array.isArray(p.offers) ? p.offers[0] : p.offers;
    if (offers) {
      out.price = num(offers.price ?? offers.lowPrice ?? offers.priceSpecification?.price);
      out.currency = offers.priceCurrency || offers.priceSpecification?.priceCurrency || null;
    }
  }

  // 2. the page's sharing tags
  const meta = (sel) => document.querySelector(sel)?.getAttribute("content") || "";
  if (!out.name) out.name = meta('meta[property="og:title"]') || document.querySelector("h1")?.textContent?.trim() || document.title;
  const og = meta('meta[property="og:image:secure_url"]') || meta('meta[property="og:image"]');
  if (og) out.images.push(abs(og));
  if (out.price == null) out.price = num(meta('meta[property="product:price:amount"]') || meta('meta[property="og:price:amount"]') || document.querySelector('[itemprop="price"]')?.getAttribute("content"));
  if (!out.currency) out.currency = meta('meta[property="product:price:currency"]') || meta('meta[property="og:price:currency"]') || document.querySelector('[itemprop="priceCurrency"]')?.getAttribute("content") || null;

  // 3. the biggest pictures on the page, in case the product photo is another one
  const big = [...document.images]
    .filter((img) => img.naturalWidth >= 250 && img.naturalHeight >= 250 && /^https?:/.test(img.currentSrc || img.src))
    .sort((a, b) => b.naturalWidth * b.naturalHeight - a.naturalWidth * a.naturalHeight)
    .slice(0, 8)
    .map((img) => abs(img.currentSrc || img.src));
  out.images.push(...big);
  out.images = [...new Set(out.images.filter((u) => /^https?:\/\//.test(u)))].slice(0, 8);
  out.name = out.name.replace(/\s+/g, " ").slice(0, 300);
  return out;
}
