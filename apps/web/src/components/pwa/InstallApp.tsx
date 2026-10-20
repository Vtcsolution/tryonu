"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import { canInstall, install, isInstalled, isIos, onInstallChange, setupPwa } from "@/lib/pwa";

const SNOOZE_KEY = "tryonu-install-snoozed";
const VISITS_KEY = "tryonu-pages-seen";
const SNOOZE_DAYS = 14;

/** Where the person is, which decides how TryOnU gets onto their home screen. */
export type Device =
  | "installed" // already opened from the home screen
  | "installable" // Chrome / Edge / Samsung: one tap
  | "ios-safari"
  | "ios-chrome" // Chrome, Edge or Firefox on an iPhone: Share is at the top
  | "in-app" // inside Instagram, TikTok, Facebook...: must open in the phone's browser first
  | "android-other"
  | "desktop";

function useInstallable(): boolean {
  return useSyncExternalStore(onInstallChange, canInstall, () => false);
}

export function useDevice(): Device | null {
  const installable = useInstallable();
  const [device, setDevice] = useState<Device | null>(null);
  useEffect(() => {
    const ua = navigator.userAgent;
    if (isInstalled()) setDevice("installed");
    else if (/FBAN|FBAV|Instagram|TikTok|musical_ly|BytedanceWebview|Line\/|Snapchat|LinkedInApp|Pinterest|GSA\//i.test(ua)) setDevice("in-app");
    else if (installable) setDevice("installable");
    else if (isIos()) setDevice(/CriOS|EdgiOS|FxiOS|OPiOS/i.test(ua) ? "ios-chrome" : "ios-safari");
    else if (/Android/i.test(ua)) setDevice("android-other");
    else setDevice("desktop");
  }, [installable]);
  return device;
}

function readNumber(key: string): number {
  try {
    return Number(localStorage.getItem(key) || 0);
  } catch {
    return 0;
  }
}

function write(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // private mode: nothing remembered, the banner just may show again
  }
}

// ------------------------------------------------------------------ the steps, drawn plainly

export function ShareIcon({ size = 18 }: { size?: number }) {
  return (
    <svg className="inline shrink-0 align-[-3px]" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-label="Share">
      <path d="M12 3v12M8 7l4-4 4 4" />
      <path d="M6 11H5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-8a1 1 0 0 0-1-1h-1" />
    </svg>
  );
}

function AddIcon() {
  return (
    <svg className="inline shrink-0 align-[-3px]" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-label="Add">
      <rect x="3.5" y="3.5" width="17" height="17" rx="4" />
      <path d="M12 8v8M8 12h8" />
    </svg>
  );
}

function Step({ n, children }: { n: number; children: ReactNode }) {
  return (
    <li className="flex items-start gap-3">
      <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-sage text-[14px] font-bold text-white">{n}</span>
      <span className="pt-0.5 text-[15.5px] leading-snug text-ink">{children}</span>
    </li>
  );
}

/** How to add TryOnU on this device, in plain steps. */
export function InstallSteps({ device }: { device: Device }) {
  if (device === "in-app") {
    return (
      <ol className="space-y-3">
        <Step n={1}>
          This page is open inside an app (Instagram, TikTok, Facebook…), which can&apos;t add it to your home screen. Tap the <b>⋯</b> or{" "}
          <b>⋮</b> menu at the top and choose <b>Open in Safari</b> (or <b>Open in browser</b>).
        </Step>
        <Step n={2}>In Safari, tap <b>Share</b> <ShareIcon /> at the bottom of the screen.</Step>
        <Step n={3}>Choose <b>Add to Home Screen</b> <AddIcon />, then tap <b>Add</b>.</Step>
      </ol>
    );
  }
  if (device === "ios-safari") {
    return (
      <ol className="space-y-3">
        <Step n={1}>Tap the <b>Share</b> button <ShareIcon /> at the bottom of Safari (on an iPad: at the top).</Step>
        <Step n={2}>Scroll down a little and tap <b>Add to Home Screen</b> <AddIcon />.</Step>
        <Step n={3}>Tap <b>Add</b> at the top right. The TryOnU icon is now on your home screen.</Step>
      </ol>
    );
  }
  if (device === "ios-chrome") {
    return (
      <ol className="space-y-3">
        <Step n={1}>Tap the <b>Share</b> button <ShareIcon /> at the top right, next to the address.</Step>
        <Step n={2}>Tap <b>Add to Home Screen</b> <AddIcon /> (scroll down if you don&apos;t see it).</Step>
        <Step n={3}>Tap <b>Add</b>. If you don&apos;t see the option, open tryonu.app in <b>Safari</b> and do the same there.</Step>
      </ol>
    );
  }
  if (device === "android-other") {
    return (
      <ol className="space-y-3">
        <Step n={1}>Open the browser&apos;s menu <b>⋮</b> (top right).</Step>
        <Step n={2}>Tap <b>Install app</b> or <b>Add to Home screen</b>.</Step>
        <Step n={3}>Tap <b>Install</b> / <b>Add</b>. Tip: Chrome shows it best.</Step>
      </ol>
    );
  }
  return (
    <ol className="space-y-3">
      <Step n={1}>In Chrome or Edge, click the <b>install</b> icon at the right end of the address bar, or open the <b>⋮</b> menu.</Step>
      <Step n={2}>Choose <b>Install TryOnU</b> (or <b>Apps → Install this site as an app</b>).</Step>
      <Step n={3}>On your phone, open <b>tryonu.app</b> and follow the steps there.</Step>
    </ol>
  );
}

// ------------------------------------------------------------------ the offer on phones

/** Runs once on every page: registers the app's service worker, and on phones
 * offers "Add TryOnU to your home screen" from the second page on. */
export function PwaSetup() {
  const pathname = usePathname();
  const device = useDevice();
  const [show, setShow] = useState(false);
  const [steps, setSteps] = useState(false);

  useEffect(() => setupPwa(), []);

  useEffect(() => {
    if (!device || device === "installed" || device === "desktop") return;
    const seen = readNumber(VISITS_KEY) + 1;
    write(VISITS_KEY, String(seen));
    const snoozed = readNumber(SNOOZE_KEY);
    const quiet = /^\/(admin|business|extension|sign-in|sign-up|app)/.test(pathname || "");
    setShow(!quiet && seen >= 2 && Date.now() > snoozed);
  }, [pathname, device]);

  if (!show || !device) return null;
  const snooze = () => {
    write(SNOOZE_KEY, String(Date.now() + SNOOZE_DAYS * 24 * 3600 * 1000));
    setShow(false);
  };
  return (
    <div className="fixed inset-x-3 bottom-[calc(var(--tabbar-h)+12px)] z-[65] max-h-[80vh] overflow-y-auto rounded-2xl border border-line bg-surface p-4 shadow-lift sm:left-auto sm:right-4 sm:w-[400px]" role="dialog" aria-label="Get the TryOnU app">
      <div className="flex items-start gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/pwa/icon-192.png" alt="" className="h-12 w-12 shrink-0 rounded-xl" />
        <div className="min-w-0 flex-1">
          <p className="text-[16px] font-semibold text-ink">Get the TryOnU app</p>
          <p className="mt-0.5 text-[13.5px] leading-snug text-muted">Free. Opens in one tap from your home screen, full screen, with notifications. No app store needed.</p>
        </div>
      </div>
      {steps && (
        <div className="mt-3 rounded-xl bg-paper-2 p-3">
          <InstallSteps device={device} />
        </div>
      )}
      <div className="mt-3 flex gap-2">
        <button type="button" onClick={snooze} className="min-h-[46px] flex-1 rounded-full border border-line-strong text-[15px] font-semibold text-ink">
          Not now
        </button>
        {device === "installable" ? (
          <button
            type="button"
            onClick={async () => {
              await install();
              setShow(false);
            }}
            className="tu-press min-h-[46px] flex-1 rounded-full bg-sage text-[15px] font-semibold text-white"
          >
            Install
          </button>
        ) : steps ? (
          <button type="button" onClick={() => setShow(false)} className="tu-press min-h-[46px] flex-1 rounded-full bg-sage text-[15px] font-semibold text-white">
            Done
          </button>
        ) : (
          <button type="button" onClick={() => setSteps(true)} className="tu-press min-h-[46px] flex-1 rounded-full bg-sage text-[15px] font-semibold text-white">
            Show me how
          </button>
        )}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ the card and the page

/** The install card: one button where the browser allows it, plain steps everywhere else. */
export function InstallAppCard({ big = false }: { big?: boolean }) {
  const device = useDevice();
  const [done, setDone] = useState(false);
  if (!device) return null;
  return (
    <div className={`rounded-[20px] border border-line bg-surface ${big ? "p-6" : "p-5"}`}>
      <div className="flex items-center gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/pwa/icon-192.png" alt="" className={big ? "h-14 w-14 rounded-2xl" : "h-11 w-11 rounded-xl"} />
        <p className={`${big ? "text-[19px]" : "text-[16px]"} font-semibold text-ink`}>The TryOnU app</p>
      </div>
      {device === "installed" || done ? (
        <p className="mt-3 text-[15px] text-ink">You&apos;re using the app ✓</p>
      ) : device === "installable" ? (
        <>
          <p className="mt-2 text-[14.5px] text-muted">One tap to add it to this device: full screen, with notifications, no app store.</p>
          <button
            type="button"
            onClick={async () => setDone(await install())}
            className="tu-press mt-4 min-h-[50px] w-full rounded-full bg-sage text-[16px] font-semibold text-white"
          >
            Install the app
          </button>
        </>
      ) : (
        <div className="mt-4">
          <InstallSteps device={device} />
        </div>
      )}
      {!big && device !== "installed" && (
        <Link href="/app" className="mt-4 block text-[14px] font-semibold text-sage-deep hover:underline">
          More about the app →
        </Link>
      )}
    </div>
  );
}

/** /app: get TryOnU on your phone. */
export function GetTheApp() {
  return (
    <section className="tu-container pb-10 pt-4 lg:py-14">
      <div className="mx-auto max-w-2xl">
        <p className="text-[13px] font-semibold uppercase tracking-[0.16em] text-sage-deep">Get the app</p>
        <h1 className="mt-2 font-display text-[clamp(32px,5vw,50px)] leading-[1.05] text-ink">
          TryOnU on your <em>home screen</em>
        </h1>
        <p className="mt-4 text-[17px] leading-relaxed text-ink-soft">
          Add TryOnU to your phone in a few seconds. It opens in one tap like any app, full screen, with notifications when someone
          likes your look or a price drops. It&apos;s free, takes almost no space, and is always up to date: no App Store or Play Store
          needed.
        </p>
        <div className="mt-8">
          <InstallAppCard big />
        </div>
        <div className="mt-8 grid gap-3 sm:grid-cols-3">
          {[
            ["One tap", "Opens straight from your home screen."],
            ["Notifications", "Likes, replies, price drops, challenge wins."],
            ["Always new", "Updates itself. Nothing to download again."],
          ].map(([t, d]) => (
            <div key={t} className="rounded-xl border border-line bg-surface p-4">
              <p className="text-[15.5px] font-semibold text-ink">{t}</p>
              <p className="mt-1 text-[14px] text-muted">{d}</p>
            </div>
          ))}
        </div>
        <p className="mt-8 text-[14px] text-muted">
          Using the app on another device? Open <b className="text-ink">tryonu.app</b> there and come back to this page:{" "}
          <b className="text-ink">tryonu.app/app</b>
        </p>
      </div>
    </section>
  );
}
