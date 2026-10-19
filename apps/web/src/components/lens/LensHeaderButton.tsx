import Link from "next/link";
import { LensIcon } from "@/components/lens/LensIcon";

/** In the header, on every page: search the shops with a photo (like Google Lens). */
export function LensHeaderButton() {
  return (
    <Link
      href="/find-look"
      prefetch={false}
      aria-label="Find a look by photo"
      title="Find a look by photo: upload a picture, get the products"
      className="grid h-10 w-10 place-items-center rounded-full text-ink-soft transition-colors hover:bg-paper-2 hover:text-ink"
    >
      <LensIcon size={21} />
    </Link>
  );
}
