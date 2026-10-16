"use client";

import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { countryFlag, countryName, countryOptions } from "@/lib/countries";

/**
 * Pick a country by typing a few letters ("pak", "united", "AE") or
 * scrolling the list. Arrow keys, Enter and Escape work; a suggested country
 * (e.g. from the visitor's location) is listed first.
 */
export function CountryPicker({
  value,
  onChange,
  label,
  hint,
  suggested,
  placeholder = "Choose your country",
  id,
}: {
  value: string;
  onChange: (code: string) => void;
  label?: string;
  hint?: string;
  suggested?: string | null;
  placeholder?: string;
  id?: string;
}) {
  const generated = useId();
  const inputId = id ?? generated;
  const listId = `${inputId}-list`;
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const options = useMemo(() => {
    const all = countryOptions();
    const q = query.trim().toLowerCase();
    const found = q
      ? all
          .filter((c) => c.name.toLowerCase().includes(q) || c.code.toLowerCase() === q)
          // names starting with what was typed first: "pak" -> Pakistan before others
          .sort((a, b) => Number(!a.name.toLowerCase().startsWith(q)) - Number(!b.name.toLowerCase().startsWith(q)))
      : all;
    const top = !q && suggested ? all.find((c) => c.code === suggested.toUpperCase()) : undefined;
    return top ? [top, ...found.filter((c) => c.code !== top.code)] : found;
  }, [query, suggested]);

  // close when clicking anywhere else
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  // keep the highlighted country in view
  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const choose = (code: string) => {
    onChange(code);
    setQuery("");
    setOpen(false);
  };

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(i + 1, options.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      if (open && options[active]) {
        e.preventDefault();
        choose(options[active].code);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
      setQuery("");
    }
  };

  const shown = open ? query : value ? `${countryFlag(value)}  ${countryName(value)}` : "";

  return (
    <div ref={boxRef} className="relative">
      {label && (
        <label htmlFor={inputId} className="mb-1.5 block text-[14px] font-medium text-ink-soft">
          {label}
        </label>
      )}
      <div className="relative">
        <input
          id={inputId}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && options[active] ? `${listId}-${options[active].code}` : undefined}
          autoComplete="off"
          value={shown}
          placeholder={value ? `${countryName(value)}: type to change` : placeholder}
          onFocus={() => {
            setOpen(true);
            setActive(0);
          }}
          onClick={() => setOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
            setActive(0);
          }}
          onKeyDown={onKey}
          className="h-11 w-full rounded-xl border border-line-strong bg-surface px-3.5 pr-10 text-[15px] text-ink outline-none transition-colors duration-200 placeholder:text-faint focus:border-sage focus:ring-2 focus:ring-sage/25"
        />
        <span className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-[13px] text-muted" aria-hidden="true">
          {open ? "▲" : "▼"}
        </span>
      </div>
      {hint && <p className="mt-1.5 text-[13px] text-muted">{hint}</p>}
      {open && (
        <ul
          ref={listRef}
          id={listId}
          role="listbox"
          className="absolute z-50 mt-1.5 max-h-64 w-full overflow-y-auto rounded-xl border border-line bg-surface py-1 shadow-lift"
        >
          {options.length === 0 && <li className="px-3.5 py-2.5 text-[14.5px] text-muted">No country matches “{query}”</li>}
          {options.map((c, i) => (
            <li
              key={c.code}
              id={`${listId}-${c.code}`}
              data-index={i}
              role="option"
              aria-selected={c.code === value}
              onMouseDown={(e) => e.preventDefault()}
              onMouseEnter={() => setActive(i)}
              onClick={() => choose(c.code)}
              className={`flex cursor-pointer items-center gap-2.5 px-3.5 py-2.5 text-[15px] ${
                i === active ? "bg-sage-tint/60 text-ink" : "text-ink-soft"
              }`}
            >
              <span className="text-[18px]" aria-hidden="true">{countryFlag(c.code)}</span>
              <span className="flex-1">{c.name}</span>
              {suggested && c.code === suggested.toUpperCase() && !query && (
                <span className="text-[12.5px] text-muted">Your location</span>
              )}
              {c.code === value && <span className="text-sage-deep" aria-hidden="true">✓</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
