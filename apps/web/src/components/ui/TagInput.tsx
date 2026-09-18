"use client";

import { useState, type KeyboardEvent } from "react";

export type TagSuggestion = string | { value: string; swatch?: string };

const valueOf = (s: TagSuggestion) => (typeof s === "string" ? s : s.value);
const same = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase();

/** Free-text tags, plus optional tap-to-add suggestions shown underneath
 * (filtered by what's being typed) so most choices never need typing. */
export function TagInput({
  values,
  onChange,
  placeholder,
  suggestions = [],
}: {
  values: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
  suggestions?: TagSuggestion[];
}) {
  const [draft, setDraft] = useState("");

  const add = (raw: string) => {
    const v = raw.trim();
    if (v && !values.some((x) => same(x, v))) onChange([...values, v]);
    setDraft("");
  };
  const remove = (v: string) => onChange(values.filter((x) => !same(x, v)));

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      add(draft);
    } else if (e.key === "Backspace" && !draft && values.length > 0) {
      onChange(values.slice(0, -1));
    }
  };

  const query = draft.trim().toLowerCase();
  const visible = suggestions.filter((s) => !query || valueOf(s).toLowerCase().includes(query));

  return (
    <div>
      <div className="flex min-h-11 flex-wrap items-center gap-2 rounded-xl border border-line-strong bg-paper px-3 py-2 focus-within:border-sage focus-within:ring-2 focus-within:ring-sage/25">
        {values.map((v) => {
          const swatch = suggestions.find((s) => typeof s !== "string" && same(s.value, v));
          return (
            <span
              key={v}
              className="tu-pop flex items-center gap-1.5 rounded-full bg-sage-tint px-2.5 py-1 text-[12px] font-medium text-sage-deep"
            >
              {swatch && typeof swatch !== "string" && swatch.swatch && <Swatch color={swatch.swatch} />}
              {v}
              <button
                type="button"
                onClick={() => remove(v)}
                aria-label={`Remove ${v}`}
                className="text-sage-deep/70 hover:text-sage-deep"
              >
                ✕
              </button>
            </span>
          );
        })}
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          onBlur={() => add(draft)}
          placeholder={values.length === 0 ? placeholder : "Add more…"}
          className="min-w-[100px] flex-1 bg-transparent text-[14px] text-ink outline-none placeholder:text-faint"
        />
      </div>

      {visible.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {visible.map((s) => {
            const value = valueOf(s);
            const on = values.some((x) => same(x, value));
            return (
              <button
                key={value}
                type="button"
                aria-pressed={on}
                // mousedown would blur the text box first and commit a half-typed draft
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => (on ? remove(value) : add(value))}
                className={`tu-press inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12.5px] ${
                  on ? "border-sage bg-sage text-white" : "border-line-strong bg-surface text-ink-soft hover:border-sage hover:text-ink"
                }`}
              >
                {typeof s !== "string" && s.swatch && <Swatch color={s.swatch} />}
                {on ? "✓ " : "+ "}
                {value}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Swatch({ color }: { color: string }) {
  return (
    <span
      aria-hidden="true"
      className="inline-block h-3 w-3 shrink-0 rounded-full border border-black/15"
      style={{ background: color }}
    />
  );
}
