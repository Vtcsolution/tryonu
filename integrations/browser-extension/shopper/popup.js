// TryOnU – Try It On: the product on this page, on your own photo.
import { api, getToken, openTryOnU, readProduct, setToken } from "./api.js";

const app = document.getElementById("app");
const who = document.getElementById("who");
let me = null;
let product = null;
let chosen = "";

const h = (tag, attrs = {}, ...children) => {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "onclick") el.addEventListener("click", v);
    else if (k === "text") el.textContent = v;
    else el.setAttribute(k, v);
  }
  children.flat().forEach((c) => c && el.append(c));
  return el;
};
const show = (...nodes) => {
  app.replaceChildren(...nodes.flat().filter(Boolean));
};
const error = (msg) => h("div", { class: "error", role: "alert", text: msg });

document.getElementById("site").addEventListener("click", (e) => {
  e.preventDefault();
  openTryOnU("/");
});
document.getElementById("disconnect").addEventListener("click", async (e) => {
  e.preventDefault();
  try {
    await api("/extension/token", { method: "DELETE" });
  } catch {
    /* already gone */
  }
  await setToken(null);
  start();
});

async function start() {
  chrome.action.setBadgeText({ text: "" });
  if (!(await getToken())) return showConnect();
  try {
    me = await api("/extension/me");
  } catch (err) {
    return err.status === 401 ? showConnect() : show(error(err.message));
  }
  who.textContent = `${me.credits} credits`;
  document.getElementById("disconnect").hidden = false;
  const { lastDone } = await chrome.storage.local.get("lastDone");
  if (lastDone) {
    await chrome.storage.local.remove("lastDone");
    return showJob(lastDone);
  }
  if (!me.has_photo) return showNeedPhoto();
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  try {
    product = tab?.id && /^https?:/.test(tab.url || "") ? await readProduct(tab.id) : null;
  } catch {
    product = null;
  }
  if (!product || product.images.length === 0) return showNoProduct();
  chosen = product.images[0];
  showProduct();
}

function showConnect() {
  who.textContent = "";
  document.getElementById("disconnect").hidden = true;
  show(
    h("h2", { text: "See it on you before you buy" }),
    h("p", { text: "Try clothes, shoes and accessories from any shop on your own photo. Connect your TryOnU account to start." }),
    h("button", { onclick: () => openTryOnU("/extension/connect?kind=shopper") }, "Connect my TryOnU account"),
    h("p", { class: "small center", text: "No account yet? You can create one on the next page." }),
  );
}

function showNeedPhoto() {
  show(
    h("h2", { text: "Add your photo first" }),
    h("p", { text: "Upload one clear photo of yourself on TryOnU (standing, facing the camera). You only do this once." }),
    h("button", { onclick: () => openTryOnU("/try") }, "Add my photo on TryOnU"),
    h("button", { class: "ghost", onclick: start }, "I've added it"),
  );
}

async function showNoProduct() {
  show(
    h("h2", { text: "Open a product page" }),
    h("p", { text: "Go to a product on eBay, AliExpress or any shop, then click the TryOnU button again." }),
    h("p", { class: "small", text: "Tip: you can also right-click any product picture and choose “Try this on with TryOnU”." }),
    await recent(),
  );
}

function showProduct(message) {
  const main = h("img", { class: "main", src: chosen, alt: "" });
  const thumbs = product.images.length > 1
    ? h(
        "div",
        { class: "thumbs" },
        product.images.map((src) =>
          h("img", {
            src,
            alt: "",
            class: src === chosen ? "on" : "",
            title: "Use this picture",
            onclick: () => {
              chosen = src;
              showProduct();
            },
          }),
        ),
      )
    : null;
  const cost = me.tryon_cost;
  const enough = me.credits >= cost;
  const price = product.price ? `${product.price} ${product.currency || ""}` : "";
  show(
    h(
      "div",
      { class: "card" },
      h("div", { class: "product" }, main, h("div", {}, h("div", { class: "name", text: product.name || "This product" }), price ? h("p", { class: "small", text: price }) : null, h("p", { class: "small", text: new URL(product.url).hostname.replace(/^www\./, "") }))),
      thumbs ? h("p", { class: "small", text: "Not the right picture? Pick another:" }) : null,
      thumbs,
    ),
    enough
      ? h("button", { id: "go", onclick: tryOn }, `Try it on · ${cost} credits`)
      : [
          h("div", { class: "error", text: `A try-on uses ${cost} credits; you have ${me.credits}.` }),
          h("button", { onclick: () => openTryOnU("/credits") }, "Buy credits"),
        ],
    message ? error(message) : null,
  );
}

async function tryOn() {
  const btn = document.getElementById("go");
  if (btn) btn.disabled = true;
  try {
    const job = await api("/extension/tryon", {
      method: "POST",
      body: {
        image_url: chosen,
        page_url: product.url,
        name: product.name,
        price_cents: product.price ? Math.round(product.price * 100) : null,
        currency: product.currency,
        description: product.description || null,
      },
    });
    chrome.runtime.sendMessage({ type: "watch", jobId: job.id });
    showJob(job.id);
  } catch (err) {
    showProduct(err.message);
  }
}

async function showJob(id) {
  let job;
  try {
    job = await api(`/extension/tryon/${id}`);
  } catch (err) {
    return show(error(err.message));
  }
  who.textContent = `${job.credits_left} credits`;
  if (job.status === "queued" || job.status === "processing") {
    show(
      h("div", { class: "center" }, h("div", { class: "spin" }), h("h2", { text: "Dressing you…" }), h("p", { text: "About 20–60 seconds. You can close this; we'll notify you." })),
    );
    setTimeout(() => showJob(id), 3000);
    return;
  }
  if (job.status === "failed") {
    return show(
      h("h2", { text: "The try-on didn't work" }),
      h("p", { text: job.error || "Please try a clearer product picture." }),
      h("p", { class: "small", text: "Your credits were given back." }),
      h("button", { onclick: start }, "Try again"),
    );
  }
  const saveBtn = h("button", { class: job.saved ? "ghost" : "" }, job.saved ? "✓ Saved to my looks" : "Save to my looks");
  if (!job.saved) {
    saveBtn.addEventListener("click", async () => {
      saveBtn.disabled = true;
      try {
        await api(`/extension/tryon/${id}/save`, { method: "POST" });
        saveBtn.textContent = "✓ Saved to my looks";
        saveBtn.className = "ghost";
      } catch (err) {
        saveBtn.disabled = false;
        saveBtn.after(error(err.message));
      }
    });
  }
  show(
    h("h2", { text: "Here's you ✨" }),
    h("p", { class: "small", text: job.product_name }),
    h("img", { class: "result", src: job.result_image_url, alt: `You wearing ${job.product_name}` }),
    saveBtn,
    h(
      "div",
      { class: "row" },
      h("button", { class: "ghost", onclick: () => chrome.tabs.create({ url: job.result_image_url }) }, "Full size"),
      h("button", { class: "ghost", onclick: () => openTryOnU("/saved") }, "My looks"),
    ),
    h("button", { class: "ghost", onclick: start }, "Try something else"),
  );
}

async function recent() {
  try {
    const items = await api("/extension/tryons?limit=4");
    if (!items.length) return null;
    return h(
      "div",
      { class: "recent" },
      h("p", { class: "small", text: "Your recent try-ons" }),
      items.map((j) =>
        h(
          "a",
          { href: "#", onclick: (e) => (e.preventDefault(), showJob(j.id)) },
          j.result_image_url ? h("img", { src: j.result_image_url, alt: "" }) : h("img", { alt: "" }),
          h("span", { text: `${j.product_name}${j.status === "completed" ? "" : ` · ${j.status}`}` }),
        ),
      ),
    );
  } catch {
    return null;
  }
}

start();
