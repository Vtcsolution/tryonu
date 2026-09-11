import { SiteChrome } from "@/components/layout/SiteChrome";
import { Hero } from "@/components/marketing/Hero";
import { TrustedBand } from "@/components/marketing/TrustedBand";
import { Section, SectionHead } from "@/components/marketing/primitives";
import { CompareSlider } from "@/components/marketing/CompareSlider";
import { Features } from "@/components/marketing/Features";
import { Marketplaces } from "@/components/marketing/Marketplaces";
import { HowItWorks } from "@/components/marketing/HowItWorks";
import { FinalCTA } from "@/components/marketing/FinalCTA";

export default function HomePage() {
  return (
    <SiteChrome>
      <Hero />
      <TrustedBand />

      <Section id="studio">
        <SectionHead
          kicker="Try-on studio"
          title={
            <>
              See it <em>on you</em>
            </>
          }
          sub="Drag the divider — same person, real product, rendered by AI. Then shop the original listing."
        />
        <CompareSlider />
      </Section>

      <Features />
      <Marketplaces />
      <HowItWorks />
      <FinalCTA />
    </SiteChrome>
  );
}
