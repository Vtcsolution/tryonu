import type { Metadata } from "next";
import { ContentPage, SectionTitle, Steps } from "@/components/content/ContentPage";
import { EarnPanel } from "@/components/content/EarnPanel";

export const metadata: Metadata = {
  title: "Invite friends & earn credits",
  description: "Share TryOnU with friends and shops. When they join from your link and use TryOnU, you earn free try-on credits.",
};

export default function EarnPage() {
  return (
    <ContentPage
      kicker="Invite & earn"
      title={
        <>
          Share TryOnU, <em>earn free credits</em>
        </>
      }
      intro="Send your link to friends, family and shops. When they join from it and use TryOnU, free credits are added to your account."
    >
      <EarnPanel />

      <div className="mt-16">
        <SectionTitle>How it works</SectionTitle>
        <Steps
          steps={[
            {
              title: "Share your link",
              text: "Copy your link, or press Share on any look you made. Send it on WhatsApp, Facebook, LinkedIn, X or email.",
            },
            {
              title: "They join",
              text: "Your friend opens the link and creates a free account. A shop can open its store on TryOnU the same way.",
            },
            {
              title: "You get credits",
              text: "When your friend does their first try-on, or the shop buys its first plan, credits are added to your account by themselves.",
            },
          ]}
        />
      </div>

      <div className="mt-16 max-w-3xl">
        <SectionTitle>Good to know</SectionTitle>
        <ul className="list-disc space-y-2 pl-6 text-[16px] leading-relaxed text-ink-soft">
          <li>You earn once for each friend (their first try-on) and once for each shop (its first plan).</li>
          <li>Your friend needs to create the account from your link, within a few days of opening it.</li>
          <li>Free try-ons paid by a shop don&apos;t count; the friend&apos;s first try-on with their own credits does.</li>
          <li>Inviting yourself, or making accounts only to collect credits, doesn&apos;t count, and we may remove those credits.</li>
          <li>Earned credits work like any other credits. They have no cash value.</li>
        </ul>
      </div>
    </ContentPage>
  );
}
