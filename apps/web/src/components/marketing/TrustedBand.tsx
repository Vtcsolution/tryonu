import { RetailerMark } from "./RetailerMark";

/** Sage band echoing the reference's "trusted by professionals" strip. */
export function TrustedBand() {
  return (
    <section className="bg-sage text-white">
      <div className="mx-auto flex w-[min(1180px,calc(100%-42px))] flex-col items-center gap-6 py-10 sm:flex-row sm:justify-between">
        <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-white/75">
          Real products from stores you already shop
        </p>
        <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-3">
          {(["Amazon", "eBay", "Flipkart", "Daraz"] as const).map((r) => (
            <span
              key={r}
              className="rounded-lg bg-white/95 px-3 py-1.5 text-[14px] text-[#1b1b18]"
            >
              <RetailerMark name={r} className="text-[14px]" />
            </span>
          ))}
          <span className="text-[13px] text-white/80">+ direct brands</span>
        </div>
      </div>
    </section>
  );
}
