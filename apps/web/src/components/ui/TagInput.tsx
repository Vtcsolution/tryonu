"use client";

import { useState, type KeyboardEvent } from "react";

export function TagInput({
  values,
  onChange,
  placeholder,
}: {
  values: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState("");

  const addTag = () => {
    const v = draft.trim();
    if (v && !values.includes(v)) onChange([...values, v]);
    setDraft("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTag();
    } else if (e.key === "Backspace" && !draft && values.length > 0) {
      onChange(values.slice(0, -1));
    }
  };

  return (
    <div className="flex min-h-11 flex-wrap items-center gap-2 rounded-xl border border-line-strong bg-paper px-3 py-2 focus-within:border-sage focus-within:ring-2 focus-within:ring-sage/25">
      {values.map((v) => (
        <span
          key={v}
          className="flex items-center gap-1.5 rounded-full bg-sage-tint px-2.5 py-1 text-[12px] font-medium text-sage-deep"
        >
          {v}
          <button
            type="button"
            onClick={() => onChange(values.filter((x) => x !== v))}
            aria-label={`Remove ${v}`}
            className="text-sage-deep/70 hover:text-sage-deep"
          >
            ✕
          </button>
        </span>
      ))}
      <input
        type="text"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKeyDown}
        onBlur={addTag}
        placeholder={values.length === 0 ? placeholder : ""}
        className="min-w-[100px] flex-1 bg-transparent text-[14px] text-ink outline-none placeholder:text-faint"
      />
    </div>
  );
}
