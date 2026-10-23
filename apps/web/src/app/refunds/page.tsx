import type { Metadata } from "next";
import Link from "next/link";
import { ContentPage, LegalBody } from "@/components/content/ContentPage";

export const metadata: Metadata = {
  title: "Refund policy",
  description: "How to get your money back for TryOnU credits, store plans and developer packs: full refund within 14 days.",
  alternates: { canonical: "/refunds" },
};

export default function RefundsPage() {
  return (
    <ContentPage kicker="Legal" title="Refund policy" intro="Changed your mind? You can get your money back within 14 days." narrow>
      <LegalBody updated="23 October 2026">
        <h2>14-day money-back</h2>
        <p>
          If you are not happy with a purchase, ask for a refund within <strong>14 days</strong> of buying it and we will give you a{" "}
          <strong>full refund</strong>. This covers try-on credit packs, store plans and developer (API) credit packs.
        </p>

        <h2>How to ask</h2>
        <ul>
          <li>
            Send us a message through the <Link href="/contact?topic=tryon">contact form</Link> or email{" "}
            <a href="mailto:sales@greatodeal.com">sales@greatodeal.com</a>, with the email of your account and the date of the purchase.
          </li>
          <li>
            If you paid through Paddle, you can also ask Paddle directly at <a href="https://paddle.net">paddle.net</a>.
          </li>
        </ul>

        <h2>What happens next</h2>
        <ul>
          <li>The money goes back to the card or account you paid with, usually within 5 to 10 working days.</li>
          <li>The credits, plan or API credits from that purchase are removed from your account.</li>
        </ul>

        <h2>Failed try-ons</h2>
        <p>
          You don&apos;t need to ask for these: if a try-on fails, its credits are returned to your account automatically.
        </p>

        <h2>Who handles payments</h2>
        <p>
          Card, Apple Pay and Google Pay payments are processed by Paddle.com, our online reseller and Merchant of Record, which also
          handles refunds for those orders. PayPal payments are processed by PayPal.
        </p>

        <h2>Contact</h2>
        <p>
          TryOnU is operated by Greatodeal AI Automation Solutions, Pakistan. Questions:{" "}
          <a href="mailto:sales@greatodeal.com">sales@greatodeal.com</a> or our <Link href="/contact">contact form</Link>.
        </p>
      </LegalBody>
    </ContentPage>
  );
}
