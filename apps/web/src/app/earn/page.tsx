import type { Metadata } from "next";
import { ContentPage, SectionTitle, Steps } from "@/components/content/ContentPage";
import { EarnPanel } from "@/components/content/EarnPanel";

export const metadata: Metadata = {
  title: "Invite friends & earn credits",
  description: "Share TryOnU with friends. When a friend who joined from your link buys credits, you earn free credits.",
};

export default function EarnPage() {
  return (
    <ContentPage
      kicker="Invite & earn"
      title={
        <>
          Share TryOnU, <em>earn credits</em>
        </>
      }
      intro="Share a look or your personal invite link with friends and on social media. When a friend who joined through your link buys credits for the first time, you earn free try-on credits."
    >
      <EarnPanel />

      <div className="mt-16">
        <SectionTitle>How it works</SectionTitle>
        <Steps
          steps={[
            {
              title: "Share your link",
              text: "Share your invite link, or any look you made: each one carries your invite. Use WhatsApp, Facebook, LinkedIn, X or email.",
            },
            { title: "A friend joins", text: "Your friend opens the link, creates a free account and can try the same products on themselves." },
            { title: "You earn credits", text: "When that friend buys credits for the first time, the reward is added to your balance automatically." },
          ]}
        />
      </div>

      <div className="mt-16 max-w-3xl">
        <SectionTitle>The rules</SectionTitle>
        <ul className="list-disc space-y-2 pl-6 text-[16px] leading-relaxed text-ink-soft">
          <li>You earn once per friend, when their first credit purchase goes through.</li>
          <li>Your friend needs to create their account through your link (or a look you shared), within a few days of opening it.</li>
          <li>Inviting yourself, or creating accounts to collect rewards, doesn&apos;t count, and we may remove rewards earned that way.</li>
          <li>Earned credits work like any other credits, and have no cash value.</li>
          <li>We may change the reward for future invites. Rewards you already earned stay yours.</li>
        </ul>
      </div>
    </ContentPage>
  );
}
