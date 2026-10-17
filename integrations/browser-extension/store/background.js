// TryOnU for Stores: right-click a product picture to add that product to your store.
import { setToken, SITE } from "./api.js";

chrome.runtime.onInstalled.addListener((details) => {
  chrome.contextMenus.create({ id: "tryonu-add", title: "Add this product to my TryOnU store", contexts: ["image"] });
  if (details.reason === "install") chrome.tabs.create({ url: `${SITE}/extension/connect?kind=store` });
});

chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg?.type === "saveToken") {
    setToken(msg.token).then(() => reply({ ok: true }));
    return true;
  }
  return false;
});

chrome.contextMenus.onClicked.addListener(async (info) => {
  if (info.menuItemId !== "tryonu-add" || !info.srcUrl) return;
  // the popup opens with this picture chosen
  await chrome.storage.local.set({ pendingImage: info.srcUrl });
  try {
    await chrome.action.openPopup();
  } catch {
    chrome.action.setBadgeText({ text: "1" });
    chrome.action.setBadgeBackgroundColor({ color: "#5f7a5b" });
  }
});
