import { forwardRef, type InputHTMLAttributes } from "react";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  error?: string;
};

export const Input = forwardRef<HTMLInputElement, Props>(function Input(
  { label, error, id, className = "", ...rest },
  ref,
) {
  return (
    <label className="block">
      {label && (
        <span className="mb-1.5 block text-[13px] font-medium text-ink-soft">{label}</span>
      )}
      <input
        ref={ref}
        id={id}
        className={`h-11 w-full rounded-xl border bg-surface px-3.5 text-[14px] text-ink outline-none transition-colors duration-200 placeholder:text-faint focus:border-sage focus:ring-2 focus:ring-sage/25 ${
          error ? "border-[#c0503a]" : "border-line-strong"
        } ${className}`}
        {...rest}
      />
      {error && <span className="mt-1.5 block text-[12px] text-[#a4553f]">{error}</span>}
    </label>
  );
});
