"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "@/lib/api/client";

/**
 * The website in the visitor's own language where English isn't widely used
 * (Saudi Arabia: Arabic, Japan: Japanese...), with one button back to
 * English. Pakistan, India and other English-using countries see nothing.
 *
 * The page's text is read after it shows, sent in small batches to the API
 * (translated once and kept there), and swapped in place; only the words
 * change, never the page's structure, so the site keeps working. Text the
 * page changes later (a menu opening, a result arriving) is translated as it
 * appears. The visitor's choice is remembered on this device.
 */

type Locale = { lang: string; name: string | null; rtl: boolean };

const CHOICE_KEY = "tryonu-lang"; // "en", or the language code the visitor chose
const SKIP_TAGS = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEXTAREA", "INPUT", "CODE", "PRE", "SVG", "IFRAME", "OPTION"]);
const ATTRS = ["placeholder", "title", "aria-label"] as const;
const HAS_LETTERS = /\p{L}{2,}/u;
const BATCH = 60;

function skip(el: Element | null): boolean {
  for (let e = el; e; e = e.parentElement) {
    if (SKIP_TAGS.has(e.tagName)) return true;
    if (e.getAttribute("translate") === "no" || e.classList.contains("notranslate") || (e as HTMLElement).isContentEditable) return true;
  }
  return false;
}

function readStore(lang: string): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(`tryonu-tr-${lang}`) || "{}");
  } catch {
    return {};
  }
}

export function AutoTranslate() {
  const pathname = usePathname();
  const [locale, setLocale] = useState<Locale | null>(null);
  const [on, setOn] = useState(false);
  const cache = useRef<Map<string, string>>(new Map());
  // for each text we changed: its English, and exactly what we wrote. A text
  // the page changed since (React re-rendering) no longer matches what we
  // wrote, so its new English is taken as the source.
  const english = useRef<WeakMap<Node, string>>(new WeakMap());
  const written = useRef<WeakMap<Node, string>>(new WeakMap());
  const attrEnglish = useRef<WeakMap<Element, Record<string, string>>>(new WeakMap());
  const attrWritten = useRef<WeakMap<Element, Record<string, string>>>(new WeakMap());
  const busy = useRef(false);

  // the language this visitor's country prefers (asked once per visit)
  useEffect(() => {
    let alive = true;
    const use = (l: Locale) => {
      if (!alive || l.lang === "en" || !l.name) return;
      setLocale(l);
      let choice: string | null = null;
      try {
        choice = localStorage.getItem(CHOICE_KEY);
      } catch {
        /* private mode */
      }
      setOn(choice !== "en");
    };
    let remembered: string | null = null;
    try {
      remembered = sessionStorage.getItem("tryonu-locale");
    } catch {
      /* private mode */
    }
    if (remembered) {
      use(JSON.parse(remembered));
    } else {
      fetch(`${API_BASE_URL}/api/v1/i18n/locale`, { credentials: "include" })
        .then((r) => (r.ok ? r.json() : null))
        .then((l: Locale | null) => {
          if (!l) return;
          try {
            sessionStorage.setItem("tryonu-locale", JSON.stringify(l));
          } catch {
            /* fine */
          }
          use(l);
        })
        .catch(() => undefined);
    }
    return () => {
      alive = false;
    };
  }, []);

  const admin = !!pathname?.startsWith("/admin");

  useEffect(() => {
    if (!locale || admin) return;
    const lang = locale.lang;
    const html = document.documentElement;

    const sourceOf = (n: Node): string => {
      const value = n.nodeValue ?? "";
      if (written.current.get(n) !== value) english.current.set(n, value);
      return english.current.get(n) ?? value;
    };
    const attrSourceOf = (el: Element, a: string): string | null => {
      const value = el.getAttribute(a);
      if (value === null) return null;
      const w = attrWritten.current.get(el) ?? {};
      const e = attrEnglish.current.get(el) ?? {};
      if (w[a] !== value) {
        e[a] = value;
        attrEnglish.current.set(el, e);
      }
      return e[a] ?? value;
    };
    const textNodes = (): Node[] => {
      const out: Node[] = [];
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      for (let n = walker.nextNode(); n; n = walker.nextNode()) if (!skip(n.parentElement)) out.push(n);
      return out;
    };
    const attrElements = () => [...document.body.querySelectorAll("[placeholder],[title],[aria-label]")].filter((el) => !skip(el));

    if (!on) {
      // back to English: every word we changed, as it was
      busy.current = true;
      for (const n of textNodes()) {
        if (written.current.get(n) === n.nodeValue) {
          n.nodeValue = english.current.get(n) ?? n.nodeValue;
          written.current.delete(n);
        }
      }
      for (const el of attrElements()) {
        const w = attrWritten.current.get(el);
        const e = attrEnglish.current.get(el);
        if (!w || !e) continue;
        for (const a of ATTRS) if (w[a] !== undefined && el.getAttribute(a) === w[a] && e[a] !== undefined) el.setAttribute(a, e[a]);
        attrWritten.current.delete(el);
      }
      busy.current = false;
      html.lang = "en";
      html.dir = "ltr";
      return;
    }

    html.lang = lang;
    html.dir = locale.rtl ? "rtl" : "ltr";
    if (cache.current.size === 0) for (const [k, v] of Object.entries(readStore(lang))) cache.current.set(k, v);

    let timer: ReturnType<typeof setTimeout> | null = null;
    let stopped = false;

    const apply = () => {
      busy.current = true;
      for (const n of textNodes()) {
        const source = sourceOf(n);
        const text = source.trim();
        const done = text && cache.current.get(text);
        if (!done) continue;
        const next = source.replace(text, done);
        if (n.nodeValue !== next) n.nodeValue = next;
        written.current.set(n, next);
      }
      for (const el of attrElements()) {
        for (const a of ATTRS) {
          const source = attrSourceOf(el, a);
          const done = source && cache.current.get(source);
          if (!done) continue;
          if (el.getAttribute(a) !== done) el.setAttribute(a, done);
          attrWritten.current.set(el, { ...(attrWritten.current.get(el) ?? {}), [a]: done });
        }
      }
      busy.current = false;
    };

    const missing = (): string[] => {
      const out = new Set<string>();
      for (const n of textNodes()) {
        const text = sourceOf(n).trim();
        if (text && text.length <= 1200 && HAS_LETTERS.test(text) && !cache.current.has(text)) out.add(text);
      }
      for (const el of attrElements()) {
        for (const a of ATTRS) {
          const v = attrSourceOf(el, a);
          if (v && v.length <= 1200 && HAS_LETTERS.test(v) && !cache.current.has(v)) out.add(v);
        }
      }
      return [...out];
    };

    const save = () => {
      try {
        localStorage.setItem(`tryonu-tr-${lang}`, JSON.stringify(Object.fromEntries([...cache.current].slice(-4000))));
      } catch {
        /* storage full or blocked: the API keeps them anyway */
      }
    };

    const run = async () => {
      apply();
      const todo = missing();
      for (let i = 0; i < todo.length && !stopped; i += BATCH) {
        const batch = todo.slice(i, i + BATCH);
        try {
          const res = await fetch(`${API_BASE_URL}/api/v1/i18n/translate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ lang, texts: batch }),
          });
          if (!res.ok) break;
          const data: { texts: string[] } = await res.json();
          batch.forEach((src, k) => cache.current.set(src, data.texts[k] ?? src));
        } catch {
          break;
        }
        if (!stopped) apply();
      }
      if (todo.length) save();
    };

    const schedule = () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(run, 200);
    };
    const observer = new MutationObserver(() => {
      if (!busy.current) schedule();
    });
    observer.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: [...ATTRS] });
    schedule();
    return () => {
      stopped = true;
      observer.disconnect();
      if (timer) clearTimeout(timer);
    };
  }, [locale, on, admin, pathname]);

  if (!locale || admin) return null;
  const choose = (next: boolean) => {
    setOn(next);
    try {
      localStorage.setItem(CHOICE_KEY, next ? locale.lang : "en");
    } catch {
      /* fine for this visit */
    }
  };
  return (
    <button
      type="button"
      translate="no"
      onClick={() => choose(!on)}
      className="notranslate fixed bottom-[calc(var(--tabbar-h,0px)+16px)] start-4 z-[60] inline-flex min-h-[40px] items-center gap-2 rounded-full border border-line-strong bg-surface px-4 text-[14.5px] font-semibold text-ink shadow-lift"
      aria-label={on ? "Show the website in English" : `Show the website in ${locale.name}`}
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="M3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3Z" />
      </svg>
      {on ? "English" : locale.name}
    </button>
  );
}
