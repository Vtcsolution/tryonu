// TryOnU for Stores: the product on this page, added to your TryOnU store.
import { api, getToken, openTryOnU, readProduct, setToken } from "./api.js";

const app = document.getElementById("app");
const who = document.getElementById("who");
const CURRENCIES = ["PKR", "USD", "EUR", "GBP", "INR", "AED", "SAR", "BDT", "CAD", "AUD"];
const CATEGORIES = ["Dresses", "Eastern wear", "Bridal", "Tops & shirts", "Trousers & jeans", "Jackets & coats", "Shoes", "Bags", "Jewellery", "Watches", "Glasses", "Accessories"];
let me = null;
let product = null;
let chosen = "";

const h = (tag, attrs = {}, ...children) => {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "onclick") el.addEventListener("click", v);
    else if (k === "text") el.textContent = v;
    else if (k === "value") el.value = v;
    else el.setAttribute(k, v);
  }
  children.flat().forEach((c) => c && el.append(c));
  return el;
};
const show = (...nodes) => app.replaceChildren(...nodes.flat().filter(Boolean));
const error = (msg) => h("div", { class: "error", role: "alert", text: msg });

document.getElementById("site").addEventListener("click", (e) => {
  e.preventDefault();
  openTryOnU("/business");
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
  document.getElementById("disconnect").hidden = false;
  if (!me.store) return showNoStore();
  who.textContent = `${me.store.products} of ${me.store.product_limit} products`;
  if (!me.store.plan_active) return showNoPlan();
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  try {
    product = tab?.id && /^https?:/.test(tab.url || "") ? await readProduct(tab.id) : null;
  } catch {
    product = null;
  }
  const { pendingImage } = await chrome.storage.local.get("pendingImage");
  if (pendingImage) {
    await chrome.storage.local.remove("pendingImage");
    product = product || { url: tab?.url || pendingImage, name: tab?.title || "", images: [], price: null, currency: null, description: "" };
    product.images = [pendingImage, ...product.images.filter((i) => i !== pendingImage)];
  }
  if (!product || product.images.length === 0) return showNoProduct();
  chosen = product.images[0];
  showForm();
}

function showConnect() {
  who.textContent = "";
  document.getElementById("disconnect").hidden = true;
  show(
    h("h2", { text: "Add products in one click" }),
    h("p", { text: "Add any product page, your own website included, to your TryOnU store. Connect your store account to start." }),
    h("button", { onclick: () => openTryOnU("/extension/connect?kind=store") }, "Connect my TryOnU store"),
  );
}

function showNoStore() {
  show(
    h("h2", { text: "Open your TryOnU store first" }),
    h("p", { text: "Create your store on TryOnU, then come back here to add products." }),
    h("button", { onclick: () => openTryOnU("/business/sign-up") }, "Open my store"),
    h("button", { class: "ghost", onclick: start }, "I've opened it"),
  );
}

function showNoPlan() {
  show(
    h("h2", { text: "Unlock a plan to add products" }),
    h("p", { text: `${me.store.name} needs an active plan before products can be added.` }),
    h("button", { onclick: () => openTryOnU("/business") }, "Choose a plan"),
  );
}

function showNoProduct() {
  show(
    h("h2", { text: "Open a product page" }),
    h("p", { text: "Go to the product on your website (or any page with the product), then click this button again." }),
    h("p", { class: "small", text: "Tip: right-click the product picture and choose “Add this product to my TryOnU store”." }),
  );
}

function showForm(message) {
  const name = h("input", { value: product.name || "", maxlength: "500" });
  const price = h("input", { type: "number", min: "0.01", step: "0.01", value: product.price ? String(product.price) : "", placeholder: "e.g. 4500" });
  const currency = h(
    "select",
    {},
    [...new Set([(product.currency || "").toUpperCase(), ...CURRENCIES].filter(Boolean))].map((c) => h("option", { value: c, text: c })),
  );
  if (product.currency) currency.value = product.currency.toUpperCase();
  const category = h("select", {}, h("option", { value: "", text: "Choose…" }), CATEGORIES.map((c) => h("option", { value: c.toLowerCase(), text: c })));
  const gender = h(
    "select",
    {},
    [["women", "Women"], ["men", "Men"], ["unisex", "Everyone"], ["girls", "Girls"], ["boys", "Boys"]].map(([v, t]) => h("option", { value: v, text: t })),
  );
  const description = h("textarea", { maxlength: "4000" });
  description.value = product.description || "";
  const thumbs = product.images.length > 1
    ? h(
        "div",
        { class: "thumbs" },
        product.images.map((src) =>
          h("img", {
            src,
            alt: "",
            class: src === chosen ? "on" : "",
            onclick: (e) => {
              chosen = src;
              e.currentTarget.parentElement.querySelectorAll("img").forEach((i) => i.classList.toggle("on", i.src === src));
              document.getElementById("main").src = src;
            },
          }),
        ),
      )
    : null;
  const add = h("button", {}, "Add to my store");
  add.addEventListener("click", async () => {
    const cents = Math.round(parseFloat(price.value) * 100);
    if (!name.value.trim() || !(cents > 0)) {
      add.after(error("Please enter the product name and price."));
      return;
    }
    add.disabled = true;
    try {
      const res = await api("/extension/store/products", {
        method: "POST",
        body: {
          name: name.value.trim(),
          price_cents: cents,
          currency: currency.value.toLowerCase(),
          product_url: product.url,
          image_url: chosen,
          description: description.value.trim() || null,
          category: category.value || null,
          gender: gender.value,
        },
      });
      who.textContent = `${res.products} of ${res.product_limit} products`;
      show(
        h("div", { class: "ok", text: `✓ “${res.name}” is now in your TryOnU store.` }),
        h("p", { class: "small", text: `${res.products} of ${res.product_limit} products used on your plan.` }),
        h("button", { onclick: () => chrome.tabs.create({ url: res.dashboard_url }) }, "See it in my dashboard"),
        h("button", { class: "ghost", onclick: start }, "Add another product"),
      );
    } catch (err) {
      add.disabled = false;
      showForm(err.message);
    }
  });
  show(
    h("div", { class: "product" }, h("img", { id: "main", class: "main", src: chosen, alt: "" }), h("div", {}, h("p", { class: "small", text: new URL(product.url).hostname.replace(/^www\./, "") }), thumbs ? h("p", { class: "small", text: "Pick the main picture:" }) : null, thumbs)),
    h("label", {}, "Product name", name),
    h("div", { class: "row" }, h("label", {}, "Price", price), h("label", {}, "Currency", currency)),
    h("div", { class: "row" }, h("label", {}, "Category", category), h("label", {}, "For", gender)),
    h("label", {}, "Description (optional)", description),
    message ? error(message) : null,
    add,
  );
}

start();
