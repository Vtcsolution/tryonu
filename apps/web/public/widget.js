/*!
 * TryOnU "Try it on" widget — https://tryonu.app/developers
 *
 *   <script src="https://tryonu.app/widget.js" data-key="tou_pk_..." defer></script>
 *   <button data-tryonu-garment="https://your-shop.com/dress.jpg" data-tryonu-name="Red dress">Try it on</button>
 *
 * data-tryonu-garment: the product photo. Leave it empty to use the page's main
 * (og:image) picture. Each try-on uses 1 credit of the shop's TryOnU account.
 * Optional on the script tag: data-button-text, data-color, data-api.
 */
(function () {
  "use strict";
  if (window.TryOnU && window.TryOnU.__loaded) return;

  var script =
    document.currentScript ||
    (function () {
      var all = document.querySelectorAll("script[src*='widget.js'][data-key]");
      return all[all.length - 1] || null;
    })();
  var KEY = (script && script.getAttribute("data-key")) || "";
  var API = ((script && script.getAttribute("data-api")) || "https://api.tryonu.app").replace(/\/+$/, "");
  var COLOR = (script && script.getAttribute("data-color")) || "#5f7a5b";
  var LABEL = (script && script.getAttribute("data-button-text")) || "Try it on";
  var ENDPOINT = API + "/api/v1/public/widget/tryons";
  var MAX_BYTES = 15 * 1024 * 1024;

  var host = null;
  var ui = null;
  var state = { garment: "", name: "", file: null, preview: "", polling: 0 };

  function pageImage() {
    var meta =
      document.querySelector("meta[property='og:image:secure_url']") ||
      document.querySelector("meta[property='og:image']") ||
      document.querySelector("meta[name='twitter:image']");
    var url = meta && meta.getAttribute("content");
    return url ? new URL(url, location.href).href : "";
  }

  var CSS =
    ":host{all:initial}" +
    "*{box-sizing:border-box;font-family:system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif}" +
    ".back{position:fixed;inset:0;z-index:2147483646;background:rgba(20,20,18,.55);display:flex;align-items:center;justify-content:center;padding:16px}" +
    ".box{position:relative;width:100%;max-width:440px;max-height:calc(100vh - 32px);overflow:auto;background:#fffdf8;color:#1f1f1c;border-radius:22px;padding:22px;box-shadow:0 20px 60px rgba(0,0,0,.3)}" +
    ".x{position:absolute;top:10px;right:10px;width:40px;height:40px;border:0;border-radius:50%;background:#efece4;color:#1f1f1c;font-size:22px;line-height:40px;cursor:pointer}" +
    "h2{margin:0 44px 4px 0;font-size:21px;font-weight:650}" +
    "p{margin:6px 0;font-size:15px;line-height:1.5;color:#4a4a44}" +
    ".row{display:flex;gap:12px;align-items:center;margin:14px 0}" +
    ".thumb{width:76px;height:96px;border-radius:12px;object-fit:cover;background:#efece4;flex:none}" +
    ".pick{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;width:100%;min-height:150px;border:2px dashed #c9c4b6;border-radius:16px;background:#f6f3ec;cursor:pointer;font-size:16px;font-weight:600;color:#1f1f1c;text-align:center;padding:14px}" +
    ".pick img{max-height:260px;max-width:100%;border-radius:12px}" +
    ".pick small{font-weight:400;color:#6b6b63;font-size:13.5px}" +
    ".go{display:block;width:100%;min-height:50px;margin-top:14px;border:0;border-radius:999px;color:#fff;font-size:17px;font-weight:650;cursor:pointer}" +
    ".go[disabled]{opacity:.45;cursor:default}" +
    ".ghost{display:inline-block;min-height:44px;margin-top:10px;padding:0 18px;border:1px solid #c9c4b6;border-radius:999px;background:#fff;color:#1f1f1c;font-size:15px;font-weight:600;line-height:42px;cursor:pointer;text-decoration:none}" +
    ".err{margin-top:12px;padding:10px 12px;border-radius:12px;background:#fbe9e4;color:#8a3422;font-size:14.5px}" +
    ".spin{width:46px;height:46px;margin:26px auto 12px;border-radius:50%;border:4px solid #e4e0d4;border-top-color:currentColor;animation:s 1s linear infinite}" +
    "@keyframes s{to{transform:rotate(360deg)}}" +
    ".center{text-align:center}" +
    ".result{display:block;width:100%;border-radius:16px;margin-top:12px;background:#efece4}" +
    ".fine{font-size:12.5px;color:#85857c;margin-top:12px}" +
    ".fine a{color:inherit}" +
    "input[type=file]{display:none}";

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs)
      Object.keys(attrs).forEach(function (k) {
        if (k === "text") node.textContent = attrs[k];
        else if (k === "on") Object.keys(attrs.on).forEach(function (e) { node.addEventListener(e, attrs.on[e]); });
        else node.setAttribute(k, attrs[k]);
      });
    (children || []).forEach(function (c) { if (c) node.appendChild(c); });
    return node;
  }

  function mount() {
    if (host) return;
    host = document.createElement("div");
    host.setAttribute("data-tryonu-widget", "");
    var root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;
    root.appendChild(el("style", { text: CSS }));
    var body = el("div", { class: "box", role: "dialog", "aria-modal": "true", "aria-label": "Try it on" });
    var back = el("div", { class: "back", on: { click: function (e) { if (e.target === back) close(); } } }, [body]);
    root.appendChild(back);
    ui = { back: back, body: body };
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && host && host.isConnected) close(); });
  }

  function close() {
    state.polling++;
    if (host && host.parentNode) host.parentNode.removeChild(host);
  }

  function paint(children) {
    ui.body.textContent = "";
    ui.body.appendChild(el("button", { class: "x", type: "button", "aria-label": "Close", text: "×", on: { click: close } }));
    children.forEach(function (c) { if (c) ui.body.appendChild(c); });
    var first = ui.body.querySelector(".go,.pick,.ghost");
    if (first && first.focus) first.focus();
  }

  function fine() {
    var f = el("p", { class: "fine" });
    f.appendChild(document.createTextNode("Your photo is only used to make this picture. Powered by "));
    f.appendChild(el("a", { href: "https://tryonu.app", target: "_blank", rel: "noopener", text: "TryOnU" }));
    return f;
  }

  function goButton(text, onClick, disabled) {
    var b = el("button", { class: "go", type: "button", text: text, on: { click: onClick } });
    b.style.background = COLOR;
    if (disabled) b.disabled = true;
    return b;
  }

  function showPick(error) {
    var input = el("input", { type: "file", accept: "image/*" });
    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (!file) return;
      if (!/^image\//.test(file.type)) return showPick("Please choose a photo (JPG or PNG).");
      if (file.size > MAX_BYTES) return showPick("This photo is too big. Please choose one under 15 MB.");
      if (state.preview) URL.revokeObjectURL(state.preview);
      state.file = file;
      state.preview = URL.createObjectURL(file);
      showPick();
    });
    var pick = el("label", { class: "pick", tabindex: "0" }, [input]);
    pick.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
    if (state.preview) {
      pick.appendChild(el("img", { src: state.preview, alt: "Your photo" }));
      pick.appendChild(el("small", { text: "Tap to change the photo" }));
    } else {
      pick.appendChild(el("span", { text: "📷  Add a photo of yourself" }));
      pick.appendChild(el("small", { text: "Standing, facing the camera, full body, good light" }));
    }
    paint([
      el("h2", { text: "See it on you" }),
      el("div", { class: "row" }, [
        el("img", { class: "thumb", src: state.garment, alt: "" }),
        el("p", { text: state.name || "This product" }),
      ]),
      pick,
      error ? el("div", { class: "err", role: "alert", text: error }) : null,
      goButton("Try it on", start, !state.file),
      fine(),
    ]);
  }

  function showWaiting() {
    var spin = el("div", { class: "spin" });
    spin.style.color = COLOR;
    paint([
      el("div", { class: "center" }, [
        spin,
        el("h2", { text: "Dressing you…" }),
        el("p", { text: "This takes about 20 to 60 seconds. Please keep this window open." }),
      ]),
    ]);
  }

  function showResult(url) {
    paint([
      el("h2", { text: "Here's how it looks on you" }),
      el("img", { class: "result", src: url, alt: "You wearing " + (state.name || "the product") }),
      el("div", { class: "center" }, [
        el("a", { class: "ghost", href: url, target: "_blank", rel: "noopener", text: "Open full size" }),
        document.createTextNode(" "),
        el("button", { class: "ghost", type: "button", text: "Try another photo", on: { click: function () { showPick(); } } }),
      ]),
      goButton("Back to the shop", close),
      fine(),
    ]);
  }

  function plain(status, body) {
    var detail = body && typeof body.detail === "string" ? body.detail : "";
    if (status === 402) return "Try-on isn't available in this shop right now. Please try again later.";
    if (status === 429) return detail || "Too many try-ons for now. Please try again in a little while.";
    if (status === 400 && detail) return detail;
    if (status === 401 || status === 403) return "Try-on isn't set up on this website yet.";
    return "Something went wrong. Please try again.";
  }

  function start() {
    if (!state.file) return;
    var form = new FormData();
    form.append("person_image", state.file);
    form.append("garment_image_url", state.garment);
    if (state.name) form.append("garment_name", state.name.slice(0, 250));
    showWaiting();
    var run = ++state.polling;
    fetch(ENDPOINT, { method: "POST", headers: { "X-TryOnU-Key": KEY }, body: form, credentials: "omit" })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (b) { return { ok: r.ok, status: r.status, body: b }; });
      })
      .then(function (res) {
        if (run !== state.polling) return;
        if (!res.ok) return showPick(plain(res.status, res.body));
        poll(res.body.id, run, Date.now());
      })
      .catch(function () { if (run === state.polling) showPick("We couldn't reach TryOnU. Please check your connection and try again."); });
  }

  function poll(id, run, startedAt) {
    if (run !== state.polling) return;
    if (Date.now() - startedAt > 4 * 60 * 1000) return showPick("This is taking too long. Please try again.");
    setTimeout(function () {
      if (run !== state.polling) return;
      fetch(ENDPOINT + "/" + encodeURIComponent(id), { headers: { "X-TryOnU-Key": KEY }, credentials: "omit" })
        .then(function (r) { return r.json().then(function (b) { return { ok: r.ok, status: r.status, body: b }; }); })
        .then(function (res) {
          if (run !== state.polling) return;
          var s = res.body && res.body.status;
          if (res.ok && s === "completed" && res.body.result_image_url) return showResult(res.body.result_image_url);
          if (res.ok && s === "failed")
            return showPick("We couldn't make this picture. Please try a clearer photo: standing, facing the camera, full body.");
          if (!res.ok && res.status !== 429 && res.status < 500) return showPick(plain(res.status, res.body));
          poll(id, run, startedAt);
        })
        .catch(function () { poll(id, run, startedAt); });
    }, 3000);
  }

  function open(options) {
    options = options || {};
    if (!KEY) {
      console.warn("TryOnU: add data-key=\"tou_pk_...\" to the widget.js script tag.");
      return;
    }
    var garment = options.garment ? new URL(options.garment, location.href).href : pageImage();
    if (!garment) {
      console.warn("TryOnU: no product photo. Set data-tryonu-garment on the button.");
      return;
    }
    mount();
    state.garment = garment;
    state.name = options.name || document.title || "";
    document.body.appendChild(host);
    showPick();
  }

  // Any element with data-tryonu-garment opens the try-on, including ones added later.
  document.addEventListener("click", function (e) {
    var target = e.target && e.target.closest ? e.target.closest("[data-tryonu-garment]") : null;
    if (!target) return;
    e.preventDefault();
    open({ garment: target.getAttribute("data-tryonu-garment"), name: target.getAttribute("data-tryonu-name") || "" });
  });

  // Empty buttons get a ready-made label and look.
  function dress() {
    var buttons = document.querySelectorAll("[data-tryonu-garment]:not([data-tryonu-ready])");
    for (var i = 0; i < buttons.length; i++) {
      var b = buttons[i];
      b.setAttribute("data-tryonu-ready", "");
      if (!b.textContent.trim()) {
        b.textContent = LABEL;
        b.style.cssText +=
          ";display:inline-flex;align-items:center;justify-content:center;min-height:46px;padding:0 22px;margin:8px 0;border:0;" +
          "border-radius:999px;background:" + COLOR + ";color:#fff;font-size:16px;font-weight:600;cursor:pointer";
      }
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", dress);
  else dress();
  if (window.MutationObserver) new MutationObserver(dress).observe(document.documentElement, { childList: true, subtree: true });

  window.TryOnU = { __loaded: true, open: open, close: close };
})();
