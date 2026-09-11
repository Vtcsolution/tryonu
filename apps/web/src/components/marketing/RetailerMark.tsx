type Props = { name: "Amazon" | "eBay" | "Flipkart" | "Daraz"; className?: string };

/** Lightweight text wordmarks for retailer chips (no third-party logo assets). */
export function RetailerMark({ name, className = "" }: Props) {
  if (name === "eBay") {
    return (
      <span
        className={`font-extrabold tracking-[-0.06em] ${className}`}
        aria-label="eBay"
      >
        <span style={{ color: "#e53238" }}>e</span>
        <span style={{ color: "#0064d2" }}>b</span>
        <span style={{ color: "#f5af02" }}>a</span>
        <span style={{ color: "#86b817" }}>y</span>
      </span>
    );
  }
  return (
    <span className={`font-semibold tracking-[-0.02em] ${className}`}>{name}</span>
  );
}
