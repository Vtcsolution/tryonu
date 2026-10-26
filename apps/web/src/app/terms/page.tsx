import type { Metadata } from "next";
import Link from "next/link";
import { ContentPage, LegalBody } from "@/components/content/ContentPage";

export const metadata: Metadata = {
  title: "Terms of use",
  description: "The rules for using TryOnU: accounts, credits, try-ons, stores, developers and shop links.",
  alternates: { canonical: "/terms" },
};

export default function TermsPage() {
  return (
    <ContentPage kicker="Legal" title="Terms of use" intro="The rules for using TryOnU. Please read them before you use the service." narrow>
      <LegalBody updated="26 October 2026">
        <p>
          TryOnU (tryonu.app) is operated by <strong>Greatodeal AI Automation Solutions</strong>, Pakistan (&quot;we&quot;, &quot;us&quot;).
        </p>
        <p>
          By creating an account or using tryonu.app, the TryOnU API, widget or plugins, you agree to these terms, our{" "}
          <Link href="/privacy">privacy policy</Link> and our <Link href="/photo-policy">photo &amp; data policy</Link>.
        </p>

        <h2>1. Your account</h2>
        <ul>
          <li>Give accurate details and keep your password safe. You are responsible for what happens in your account.</li>
          <li>Anyone under 16 may use TryOnU only with a parent&apos;s or guardian&apos;s permission.</li>
          <li>We may suspend accounts that break these terms or put other people or the service at risk.</li>
        </ul>

        <h2>2. Photos you upload</h2>
        <ul>
          <li>Upload only photos of yourself, or of people who have given you permission (for a child: only if you are their parent or guardian).</li>
          <li>Do not upload nude, sexual, violent or hateful images, or try to make such pictures with TryOnU.</li>
          <li>You keep the rights to your photos. You allow us to use them only to provide the service to you, as described in our photo &amp; data policy.</li>
        </ul>

        <h2>3. Try-on pictures are previews</h2>
        <p>
          Try-on pictures are made by AI. They show how a product may look on you, but the fit, size, colour and details of the real
          product can differ. Always check the store&apos;s product details and size chart before you buy.
        </p>

        <h2>4. Credits and payments</h2>
        <ul>
          <li>Try-ons use credits. The price of a try-on in credits is shown before you start.</li>
          <li>If a try-on fails, its credits are returned automatically.</li>
          <li>Credits have no cash value, can&apos;t be transferred or exchanged for money, and are used only on TryOnU.</li>
          <li>You can get a full refund within 14 days of a purchase. See our <Link href="/refunds">refund policy</Link>.</li>
          <li>
            Our order process is conducted by our online reseller <strong>Paddle.com</strong>. Paddle.com is the Merchant of Record
            for all orders paid by card, Apple Pay or Google Pay, and provides customer service enquiries and handles returns for
            those orders. PayPal payments are processed by PayPal under PayPal&apos;s own terms.
          </li>
        </ul>

        <h2>5. Shopping through TryOnU</h2>
        <p>
          TryOnU does not sell products. When you click a shop link, you buy directly from that store or marketplace, under its terms,
          prices, delivery and return policies. We are not responsible for the store&apos;s products or service. TryOnU may earn a
          commission from those links; see our <Link href="/affiliate-disclosure">affiliate disclosure</Link>.
        </p>

        <h2>6. Stores on TryOnU</h2>
        <ul>
          <li>Stores must list only real products they are allowed to sell, with honest prices, photos and delivery areas.</li>
          <li>We review stores and may remove products or stores that mislead shoppers or break the law.</li>
          <li>Store plans run for the period shown when you buy them. Try-on pictures are shared with a store only when the shopper agrees.</li>
        </ul>

        <h2>7. Developers</h2>
        <ul>
          <li>Keep secret API keys on your server. Website keys work only on the domains you register.</li>
          <li>You must get your users&apos; permission before sending their photos to TryOnU, and follow the same photo rules as above.</li>
          <li>API credits are prepaid; a failed try-on is not charged. We may limit or suspend use that harms the service.</li>
        </ul>

        <h2>8. Invite &amp; earn</h2>
        <p>
          Reward credits are given as described on the <Link href="/earn">Invite &amp; earn page</Link>. We may cancel rewards gained
          through fake accounts, self-invites or other abuse, and change the reward for future invites.
        </p>

        <h2>9. Acceptable use</h2>
        <p>
          Don&apos;t misuse TryOnU: no attempts to break or overload it, copy it in bulk, get around limits or payments, or use it to
          harass, impersonate or deceive anyone.
        </p>

        <h2>10. Our content and brand</h2>
        <ul>
          <li>
            TryOnU, including its design, layout, text, pictures, logo, software and code, belongs to Greatodeal AI Automation
            Solutions and is protected by copyright and trademark law. &quot;TryOnU&quot; and the TryOnU logo are our trademarks.
          </li>
          <li>
            You may not copy, reproduce, scrape, resell or imitate TryOnU or any part of it, or use our name or logo, without our
            written permission. This includes building a copy of our website, app or design.
          </li>
          <li>
            We act against copying, including takedown requests to search engines, hosting companies and app stores, and legal
            action where needed.
          </li>
          <li>Products, photos and brands of stores and retailers shown on TryOnU belong to their owners.</li>
        </ul>

        <h2>11. Our responsibility</h2>
        <p>
          We work hard to keep TryOnU available and accurate, but we provide it &quot;as is&quot; and can&apos;t promise it will always
          be available or error-free. To the extent the law allows, we are not liable for indirect losses, and our total liability is
          limited to the amount you paid us in the 12 months before the claim. Nothing here limits rights you have by law that
          can&apos;t be limited.
        </p>

        <h2>12. Changes and ending</h2>
        <p>
          We may update these terms; for important changes we will tell you before they apply. You can stop using TryOnU at any time
          and ask us to delete your account.
        </p>

        <h2>13. Contact</h2>
        <p>
          Questions about these terms? <Link href="/contact">Send us a message</Link> or email{" "}
          <a href="mailto:sales@greatodeal.com">sales@greatodeal.com</a>.
        </p>
      </LegalBody>
    </ContentPage>
  );
}
