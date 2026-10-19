import { AppTabBar } from "@/components/app/AppTabBar";
import { Navbar } from "@/components/marketing/Navbar";
import { Footer } from "@/components/marketing/Footer";

/** Shared page shell. Computers: sticky navbar + content + footer. Phones: an
 * app — a slim top bar, the content, and tabs at the bottom (the footer's links
 * live in the "Me" tab there). */
export function SiteChrome({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Navbar />
      <main className="tu-enter pb-[var(--tabbar-h)] lg:pb-0">{children}</main>
      <Footer />
      <AppTabBar />
    </>
  );
}
