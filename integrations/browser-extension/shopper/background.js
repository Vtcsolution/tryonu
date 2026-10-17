// TryOnU – Try It On: right-click any product picture to try it on, and a
// notification when a try-on started that way is ready.
import { api, setToken, SITE } from "./api.js";

chrome.runtime.onInstalled.addListener((details) => {
  chrome.contextMenus.create({ id: "tryonu-tryon", title: "Try this on with TryOnU", contexts: ["image"] });
  if (details.reason === "install") chrome.tabs.create({ url: `${SITE}/extension/connect?kind=shopper` });
});

chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg?.type === "saveToken") {
    setToken(msg.token).then(() => reply({ ok: true }));
    return true;
  }
  if (msg?.type === "watch") {
    watch(msg.jobId).then(() => reply({ ok: true }));
    return true;
  }
  return false;
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "tryonu-tryon" || !info.srcUrl) return;
  try {
    const job = await api("/extension/tryon", {
      method: "POST",
      body: { image_url: info.srcUrl, page_url: info.pageUrl || tab?.url || info.srcUrl, name: tab?.title || "" },
    });
    await watch(job.id);
    notify("tryonu-started", "Dressing you…", "Your try-on takes about 20–60 seconds. We'll show it here when it's ready.");
  } catch (err) {
    if (err.status === 401) chrome.tabs.create({ url: `${SITE}/extension/connect?kind=shopper` });
    notify("tryonu-error", "Couldn't start the try-on", err.message);
  }
});

// ------------------------------------------------------------------ waiting for results

async function watch(jobId) {
  const { watching = [] } = await chrome.storage.local.get("watching");
  if (!watching.includes(jobId)) watching.push(jobId);
  await chrome.storage.local.set({ watching });
  chrome.alarms.create("tryonu-poll", { periodInMinutes: 0.5 });
}

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== "tryonu-poll") return;
  const { watching = [] } = await chrome.storage.local.get("watching");
  const still = [];
  for (const id of watching) {
    try {
      const job = await api(`/extension/tryon/${id}`);
      if (job.status === "completed") {
        notify(`tryonu-done-${id}`, "Your try-on is ready ✨", `${job.product_name}. Open TryOnU to see it.`);
        await chrome.storage.local.set({ lastDone: id });
        chrome.action.setBadgeText({ text: "✓" });
        chrome.action.setBadgeBackgroundColor({ color: "#5f7a5b" });
      } else if (job.status === "failed") {
        notify(`tryonu-failed-${id}`, "The try-on didn't work", "Your credits were given back. Try a clearer product photo.");
      } else {
        still.push(id);
      }
    } catch {
      still.push(id);
    }
  }
  await chrome.storage.local.set({ watching: still });
  if (still.length === 0) chrome.alarms.clear("tryonu-poll");
});

chrome.notifications.onClicked.addListener(async (id) => {
  if (!id.startsWith("tryonu-done-")) return;
  try {
    const job = await api(`/extension/tryon/${id.slice("tryonu-done-".length)}`);
    if (job.result_image_url) chrome.tabs.create({ url: job.result_image_url });
  } catch {
    /* nothing to open */
  }
});

function notify(id, title, message) {
  chrome.notifications.create(id, { type: "basic", iconUrl: "icons/icon128.png", title, message });
}
