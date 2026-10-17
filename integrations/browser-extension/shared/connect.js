// Runs only on https://tryonu.app/extension/connect: tells the page this
// extension is installed, and receives the sign-in token the page creates for it.
(() => {
  const KIND = globalThis.TRYONU_KIND || "shopper"; // set by kind.js, one per package
  document.documentElement.setAttribute(`data-tryonu-${KIND}`, chrome.runtime.getManifest().version);
  window.postMessage({ source: "tryonu-extension", type: "installed", kind: KIND }, location.origin);

  window.addEventListener("message", (event) => {
    if (event.source !== window || event.origin !== location.origin) return;
    const msg = event.data || {};
    if (msg.source !== "tryonu-web" || msg.type !== "connect" || msg.kind !== KIND || typeof msg.token !== "string") return;
    if (!msg.token.startsWith("tou_ext_")) return;
    chrome.runtime.sendMessage({ type: "saveToken", token: msg.token }, () => {
      window.postMessage({ source: "tryonu-extension", type: "connected", kind: KIND }, location.origin);
    });
  });
})();
