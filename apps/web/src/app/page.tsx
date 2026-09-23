import { SiteChrome } from "@/components/layout/SiteChrome";
import { Hero } from "@/components/marketing/Hero";
import { TrustedBand } from "@/components/marketing/TrustedBand";
import { Section, SectionHead } from "@/components/marketing/primitives";
import { CompareSlider } from "@/components/marketing/CompareSlider";
import { Features } from "@/components/marketing/Features";
import { Marketplaces } from "@/components/marketing/Marketplaces";
import { HowItWorks } from "@/components/marketing/HowItWorks";
import { FinalCTA } from "@/components/marketing/FinalCTA";

// `value` isn't part of React's <meta> typing (the standard attribute is
// `content`), so the props are spread from here.
const IMPACT_SITE_VERIFICATION = {
  name: "impact-site-verification",
  value: "bb9a2fff-6d9d-440c-b556-a52fa0297c6e",
};

export default function HomePage() {
  return (
    <SiteChrome>
      {/* Impact.com site verification. Written as a literal element rather
          than through Next's metadata API because Impact's tag carries the
          token in `value`, and the metadata API only ever emits `content`.
          React hoists it into <head>. */}
      <meta {...IMPACT_SITE_VERIFICATION} />
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
