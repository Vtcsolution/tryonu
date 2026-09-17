"use client";

import { forwardRef, useId, useState, type InputHTMLAttributes } from "react";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  label?: string;
  error?: string;
};

/** Same look as `Input`, but for passwords — adds a show/hide toggle so
 * typos are easy to catch before submitting. */
export const PasswordInput = forwardRef<HTMLInputElement, Props>(function PasswordInput(
  { label, error, id, className = "", ...rest },
  ref,
) {
  const [visible, setVisible] = useState(false);
  const generatedId = useId();
  const inputId = id ?? generatedId;

  // The toggle button must stay outside the <label>: nested inside it, the
  // input's accessible name becomes "Password Show password".
  return (
    <div>
      {label && (
        <label htmlFor={inputId} className="mb-1.5 block text-[13px] font-medium text-ink-soft">
          {label}
        </label>
      )}
      <div className="relative">
        <input
          ref={ref}
          id={inputId}
          type={visible ? "text" : "password"}
          className={`h-11 w-full rounded-xl border bg-surface px-3.5 pr-11 text-[14px] text-ink outline-none transition-colors duration-200 placeholder:text-faint focus:border-sage focus:ring-2 focus:ring-sage/25 ${
            error ? "border-[#c0503a]" : "border-line-strong"
          } ${className}`}
          {...rest}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          tabIndex={-1}
          className="absolute inset-y-0 right-0 grid w-11 place-items-center text-ink-soft transition-colors hover:text-ink"
        >
          {visible ? <EyeOffIcon /> : <EyeIcon />}
        </button>
      </div>
      {error && <span className="mt-1.5 block text-[12px] text-[#a4553f]">{error}</span>}
    </div>
  );
});

function EyeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M3 3l18 18M10.6 5.2A10.6 10.6 0 0 1 12 5c6.4 0 10 7 10 7a17.2 17.2 0 0 1-3.7 4.6M6.6 6.6C4 8.3 2 12 2 12s3.6 7 10 7a9.9 9.9 0 0 0 4.4-1M9.9 9.9a3 3 0 0 0 4.2 4.2"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
