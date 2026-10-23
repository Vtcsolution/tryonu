import type { Metadata } from "next";
import Link from "next/link";
import { ContentPage, LegalBody } from "@/components/content/ContentPage";

export const metadata: Metadata = {
  title: "Privacy policy",
  description: "What personal information TryOnU collects, why, who it is shared with, and your choices.",
  alternates: { canonical: "/privacy" },
};

export default function PrivacyPage() {
  return (
    <ContentPage kicker="Legal" title="Privacy policy" intro="What we collect, why we collect it, and the choices you have." narrow>
      <LegalBody updated="23 October 2026">
        <p>
          This policy explains how TryOnU, operated by Greatodeal AI Automation Solutions, Pakistan (&quot;we&quot;, &quot;us&quot;), handles personal information when you use tryonu.app, the
          try-on API, the website widget and our plugins. For how we treat your photos in particular, also see our{" "}
          <Link href="/photo-policy">Photo &amp; data policy</Link>.
        </p>

        <h2>1. What we collect</h2>
        <ul>
          <li><strong>Account details:</strong> your name, email address, country, and a password (stored only in scrambled form) or your Google sign-in.</li>
          <li><strong>Photos you upload</strong> and the try-on pictures we make from them.</li>
          <li><strong>Your activity:</strong> products you try on, looks you save or share, style preferences you choose, and AI Stylist requests.</li>
          <li><strong>Purchases:</strong> what you bought and when. Payments are handled by Paddle and PayPal; we never see or store your card details.</li>
          <li><strong>Technical data:</strong> pages visited, device and browser type, approximate location from your IP address, and cookies needed to keep you signed in.</li>
          <li><strong>Messages</strong> you send us through the contact form.</li>
        </ul>

        <h2>2. Why we use it</h2>
        <ul>
          <li>To make your try-ons and show you products that fit your request, style and country.</li>
          <li>To run your account, credits and payments, and to send account emails (such as verifying your email).</li>
          <li>To keep the service safe, prevent abuse and fraud, and fix problems.</li>
          <li>To understand how TryOnU is used, in aggregate, and improve it.</li>
          <li>To answer your messages.</li>
        </ul>
        <p>We do not sell your personal information.</p>

        <h2>3. Who we share it with</h2>
        <ul>
          <li><strong>AI providers</strong> that create the try-on picture, receive your photo and the product image only to make that picture.</li>
          <li><strong>Paddle</strong> (our reseller for card, Apple Pay and Google Pay) and <strong>PayPal</strong> process payments. <strong>Google</strong> handles Google sign-in if you choose it.</li>
          <li><strong>Hosting and email providers</strong> that run our servers and send our emails.</li>
          <li><strong>Stores and shops:</strong> when you click a shop link, you go to that store, which has its own privacy policy. A store on TryOnU sees your try-on picture only if you choose a free try-on that the store pays for and agree to share it.</li>
          <li><strong>People you share with:</strong> a look you share is visible to anyone with its link until you stop sharing it.</li>
          <li><strong>Authorities,</strong> when the law requires it.</li>
        </ul>

        <h2>4. How long we keep it</h2>
        <p>
          We keep your account information while your account is open. You can delete your photos, saved looks and wardrobe items at
          any time. When you ask us to delete your account, we delete your personal information, except records we must keep by law
          (for example, payment records).
        </p>

        <h2>5. Your choices and rights</h2>
        <ul>
          <li>See and update your account details on the <Link href="/account">account page</Link>.</li>
          <li>Delete photos, looks and wardrobe items yourself, and stop sharing any look at any time.</li>
          <li>Ask us for a copy of your data, to correct it, or to delete your account, through the <Link href="/contact?topic=privacy">contact form</Link> (topic: Privacy and my data).</li>
          <li>Depending on where you live, you may have further rights under local law, such as to object to processing or to complain to a data protection authority.</li>
        </ul>

        <h2>6. Cookies</h2>
        <p>
          We use essential cookies to keep you signed in and secure, and your browser&apos;s storage to remember settings such as dark
          mode and the invite link you came from. To count visits, we keep a random visitor number in your browser; it is not linked
          to your name. We do not use advertising cookies.
        </p>

        <h2>7. Children</h2>
        <p>
          TryOnU is meant for adults. Anyone under 16 should use it only with the permission and supervision of a parent or guardian,
          and photos of children may be uploaded only by their parent or guardian.
        </p>

        <h2>8. Security</h2>
        <p>
          We protect your information with encrypted connections, restricted access and private storage for photos. No service can be
          perfectly secure, so please use a strong password and keep it to yourself.
        </p>

        <h2>9. Changes</h2>
        <p>If we change this policy in an important way, we will tell you on the site or by email before the change applies.</p>

        <h2>10. Contact</h2>
        <p>
          Questions about privacy? <Link href="/contact?topic=privacy">Send us a message</Link>.
        </p>
      </LegalBody>
    </ContentPage>
  );
}
