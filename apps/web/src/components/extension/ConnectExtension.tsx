"use client";

import { CheckIcon } from "@/components/ui/Icons";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api/client";
import { extension, type ExtensionKind } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";

const NAMES: Record<ExtensionKind, string> = { shopper: "TryOnU – Try It On", store: "TryOnU for Stores" };

function browserLabel(): string {
  const ua = navigator.userAgent;
  const browser = /Edg\//.test(ua) ? "Edge" : /OPR\//.test(ua) ? "Opera" : /Chrome\//.test(ua) ? "Chrome" : /Firefox\//.test(ua) ? "Firefox" : "Browser";
  const os = /Windows/.test(ua) ? "Windows" : /Mac OS/.test(ua) ? "Mac" : /Android/.test(ua) ? "Android" : /Linux/.test(ua) ? "Linux" : "";
  return os ? `${browser} on ${os}` : browser;
}

/** /extension/connect: links the TryOnU extensions installed in this browser to
 * the signed-in account. The token goes only to our own extension's script on
 * this page (same window, same origin), never into a link. */
export function ConnectExtension() {
  const { user, isLoading } = useSession();
  const [installed, setInstalled] = useState<ExtensionKind[]>([]);
  const [looked, setLooked] = useState(false);
  const [connected, setConnected] = useState<ExtensionKind[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const seen = () => {
      const kinds: ExtensionKind[] = [];
      if (document.documentElement.hasAttribute("data-tryonu-shopper")) kinds.push("shopper");
      if (document.documentElement.hasAttribute("data-tryonu-store")) kinds.push("store");
      setInstalled(kinds);
    };
    const onMessage = (e: MessageEvent) => {
      if (e.source !== window || e.origin !== window.location.origin) return;
      const msg = e.data || {};
      if (msg.source !== "tryonu-extension") return;
      if (msg.type === "installed") seen();
      if (msg.type === "connected" && (msg.kind === "shopper" || msg.kind === "store")) {
        setConnected((c) => (c.includes(msg.kind) ? c : [...c, msg.kind]));
      }
    };
    window.addEventListener("message", onMessage);
    seen();
    const t = setTimeout(() => {
      seen();
      setLooked(true);
    }, 1500);
    return () => {
      window.removeEventListener("message", onMessage);
      clearTimeout(t);
    };
  }, []);

  const connect = async () => {
    setBusy(true);
    setError(null);
    try {
      for (const kind of installed) {
        const { token } = await extension.connect(kind, browserLabel());
        window.postMessage({ source: "tryonu-web", type: "connect", kind, token }, window.location.origin);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't connect. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const box = "mx-auto w-[min(560px,calc(100%-32px))] py-16 text-center md:py-24";

  if (isLoading || !looked) {
    return (
      <section className={box}>
        <div className="mx-auto h-9 w-9 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
      </section>
    );
  }
  if (!user) {
    const next = encodeURIComponent(`/extension/connect${window.location.search}`);
    return (
      <section className={box}>
        <h1 className="font-display text-[clamp(26px,4vw,36px)] text-ink">Connect the TryOnU extension</h1>
        <p className="mt-3 text-[16.5px] text-ink-soft">Sign in, or create a free account, to connect it.</p>
        <div className="mt-7 flex flex-wrap justify-center gap-3">
          <Button href={`/sign-in?next=${next}`} size="lg">Sign in</Button>
          <Button href={`/sign-up?next=${next}`} size="lg" variant="outline">Create account</Button>
        </div>
      </section>
    );
  }
  if (installed.length === 0) {
    return (
      <section className={box}>
        <h1 className="font-display text-[clamp(26px,4vw,36px)] text-ink">We can&apos;t see the extension</h1>
        <p className="mt-3 text-[16.5px] text-ink-soft">
          Install the TryOnU extension in this browser first, then open this page again (or reload it).
        </p>
        <div className="mt-7 flex flex-wrap justify-center gap-3">
          <Button href="/extension" size="lg">Get the extension</Button>
          <Button size="lg" variant="outline" onClick={() => window.location.reload()}>Reload</Button>
        </div>
      </section>
    );
  }
  const done = installed.every((k) => connected.includes(k));
  return (
    <section className={box}>
      {done ? (
        <>
          <div className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-sage text-[30px] text-white"><CheckIcon size={30} /></div>
          <h1 className="mt-5 font-display text-[clamp(26px,4vw,36px)] text-ink">Connected</h1>
          <p className="mt-3 text-[16.5px] text-ink-soft">
            {installed.map((k) => NAMES[k]).join(" and ")} {installed.length > 1 ? "are" : "is"} connected to {user.email}. You can
            close this tab.
          </p>
          <div className="mt-6 rounded-[20px] border border-line bg-surface p-5 text-left text-[15.5px] leading-relaxed text-ink-soft">
            <p className="font-semibold text-ink">What next?</p>
            {installed.includes("shopper") && (
              <p className="mt-2">
                Open a product on eBay, AliExpress or any shop and click the <b>TryOnU</b> button in your browser&apos;s toolbar (pin it
                with the puzzle-piece icon), or right-click the product picture.
              </p>
            )}
            {installed.includes("store") && (
              <p className="mt-2">
                Open a product on your own website and click <b>TryOnU for Stores</b> to add it to your TryOnU store.
              </p>
            )}
          </div>
        </>
      ) : (
        <>
          <h1 className="font-display text-[clamp(26px,4vw,36px)] text-ink">Connect to your TryOnU account</h1>
          <p className="mt-3 text-[16.5px] text-ink-soft">
            Found in this browser: <b className="text-ink">{installed.map((k) => NAMES[k]).join(" and ")}</b>. It will use the account{" "}
            <b className="text-ink">{user.email}</b>
            {installed.includes("shopper") ? " and its credits" : ""}.
          </p>
          <Button size="lg" className="mt-7" disabled={busy} onClick={connect}>
            {busy ? "Connecting…" : "Connect this browser"}
          </Button>
          {error && <p className="mt-4 text-[14.5px] text-[#a4553f]">{error}</p>}
        </>
      )}
    </section>
  );
}
