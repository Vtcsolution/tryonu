"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";
import { canInstall, install, isInstalled, isIos, onInstallChange, setupPwa } from "@/lib/pwa";

const SNOOZE_KEY = "tryonu-install-snoozed";
const VISITS_KEY = "tryonu-pages-seen";
const SNOOZE_DAYS = 14;

function useInstallable(): boolean {
  return useSyncExternalStore(onInstallChange, canInstall, () => false);
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

/** Runs once on every page: registers the app's service worker, and on phones
 * offers "Add TryOnU to your home screen" after a few pages (not on the first). */
export function PwaSetup() {
  const pathname = usePathname();
  const installable = useInstallable();
  const [show, setShow] = useState(false);
  const [ios, setIos] = useState(false);
  const [steps, setSteps] = useState(false);

  useEffect(() => setupPwa(), []);

  useEffect(() => {
    if (isInstalled()) return;
    const seen = readNumber(VISITS_KEY) + 1;
    write(VISITS_KEY, String(seen));
    const snoozed = readNumber(SNOOZE_KEY);
    const phone = window.matchMedia("(max-width: 1023px)").matches;
    const quiet = /^\/(admin|business|extension|sign-in|sign-up)/.test(pathname || "");
    const iosPhone = isIos();
    setIos(iosPhone);
    setShow(phone && !quiet && seen >= 3 && Date.now() > snoozed && (installable || iosPhone));
  }, [pathname, installable]);

  if (!show) return null;
  const snooze = () => {
    write(SNOOZE_KEY, String(Date.now() + SNOOZE_DAYS * 24 * 3600 * 1000));
    setShow(false);
  };
  return (
    <div className="fixed inset-x-3 bottom-3 z-[65] rounded-2xl border border-line bg-surface p-4 shadow-lift sm:left-auto sm:right-4 sm:w-[380px]" role="dialog" aria-label="Install TryOnU">
      <div className="flex items-start gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/pwa/icon-192.png" alt="" className="h-12 w-12 shrink-0 rounded-xl" />
        <div className="min-w-0 flex-1">
          <p className="text-[15.5px] font-semibold text-ink">Add TryOnU to your home screen</p>
          <p className="mt-0.5 text-[13.5px] leading-snug text-muted">Opens in one tap, full screen, like an app. Free, no app store needed.</p>
        </div>
      </div>
      {steps && <IosSteps />}
      <div className="mt-3 flex gap-2">
        <button type="button" onClick={snooze} className="min-h-[44px] flex-1 rounded-full border border-line-strong text-[14.5px] font-semibold text-ink">
          Not now
        </button>
        {ios ? (
          !steps && (
            <button type="button" onClick={() => setSteps(true)} className="tu-press min-h-[44px] flex-1 rounded-full bg-sage text-[14.5px] font-semibold text-white">
              Show me how
            </button>
          )
        ) : (
          <button
            type="button"
            onClick={async () => {
              await install();
              setShow(false);
            }}
            className="tu-press min-h-[44px] flex-1 rounded-full bg-sage text-[14.5px] font-semibold text-white"
          >
            Install
          </button>
        )}
      </div>
    </div>
  );
}

function IosSteps() {
  return (
    <ol className="mt-3 space-y-1.5 rounded-xl bg-paper-2 p-3 text-[14px] text-ink">
      <li>
        1. Tap the <b>Share</b> button{" "}
        <svg className="inline align-[-3px]" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-label="Share">
          <path d="M12 3v12M8 7l4-4 4 4" />
          <path d="M6 11H5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-8a1 1 0 0 0-1-1h-1" />
        </svg>{" "}
        at the bottom (or top) of Safari.
      </li>
      <li>
        2. Choose <b>Add to Home Screen</b>.
      </li>
      <li>
        3. Tap <b>Add</b>. TryOnU is now on your home screen.
      </li>
    </ol>
  );
}

/** On the notifications page: install the app on this device. */
export function InstallAppCard() {
  const installable = useInstallable();
  const [state, setState] = useState<{ installed: boolean; ios: boolean } | null>(null);
  useEffect(() => setState({ installed: isInstalled(), ios: isIos() }), []);
  if (!state) return null;
  return (
    <div className="rounded-[20px] border border-line bg-surface p-5">
      <div className="flex items-center gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/pwa/icon-192.png" alt="" className="h-11 w-11 rounded-xl" />
        <p className="text-[16px] font-semibold text-ink">The TryOnU app</p>
      </div>
      {state.installed ? (
        <p className="mt-2 text-[14px] text-muted">You&apos;re using the app. ✓</p>
      ) : installable ? (
        <>
          <p className="mt-2 text-[14px] text-muted">Add TryOnU to this device: one tap to open, full screen, no app store.</p>
          <button
            type="button"
            onClick={async () => {
              if (await install()) setState({ ...state, installed: true });
            }}
            className="tu-press mt-3 min-h-[44px] w-full rounded-full bg-sage text-[15px] font-semibold text-white"
          >
            Install the app
          </button>
        </>
      ) : state.ios ? (
        <>
          <p className="mt-2 text-[14px] text-muted">Add TryOnU to your iPhone or iPad home screen:</p>
          <IosSteps />
        </>
      ) : (
        <p className="mt-2 text-[14px] text-muted">
          Open tryonu.app in Chrome on your phone and choose <b>Install app</b> (or <b>Add to Home screen</b>) from the ⋮ menu.
        </p>
      )}
    </div>
  );
}
