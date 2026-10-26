import type { Metadata } from "next";
import Link from "next/link";
import { ContentPage, LegalBody } from "@/components/content/ContentPage";

export const metadata: Metadata = {
  title: "Photo & data policy",
  description: "How TryOnU treats the photos you upload and the try-on pictures made from them.",
  alternates: { canonical: "/photo-policy" },
};

export default function PhotoPolicyPage() {
  return (
    <ContentPage
      kicker="Legal"
      title="Photo & data policy"
      intro="Your photos show your face and body. Here is exactly what happens to them."
      narrow
    >
      <LegalBody updated="26 October 2026">
        <h2>In short</h2>
        <ul>
          <li>Your photos are used only to make your try-ons.</li>
          <li>We never sell your photos, and we don&apos;t use them to train our own AI models.</li>
          <li>Other people never see your photos or try-on pictures unless you choose to share them.</li>
          <li>A few TryOnU staff can look at them only to help you with a problem or to keep TryOnU safe.</li>
          <li>You can delete them at any time.</li>
        </ul>

        <h2>1. When you upload a photo</h2>
        <p>
          Your photo is stored privately and linked to your account. Links to it are temporary and signed, so they stop working after a
          short time. Only a few TryOnU staff can open it, and only to help you (for example when a try-on went wrong) or to stop
          misuse.
        </p>

        <h2>2. When you try something on</h2>
        <p>
          To make the try-on picture, your photo and the product&apos;s image are sent to the AI provider that creates the picture. The
          provider uses them only to make that picture for us. The result is stored privately in your account.
        </p>

        <h2>3. When you share a look</h2>
        <p>
          A look becomes visible to others only when you press <strong>Share</strong>. Anyone with its link can then see the picture and
          the products in it. Press <strong>Stop sharing</strong> and the link and picture stop working right away (link previews already
          shown in other apps may take a few minutes to disappear).
        </p>

        <h2>4. Free try-ons paid by a store</h2>
        <p>
          Some stores pay for shoppers&apos; try-ons of their products. Before you start such a try-on, we tell you that the try-on
          picture will be shared with that store. If you don&apos;t want that, choose to try on with your own credits instead and nothing
          is shared.
        </p>

        <h2>5. Try-ons on other websites</h2>
        <p>
          Shops can offer TryOnU try-on on their own websites and apps through our API or widget. There, the shop is responsible for
          asking your permission, and the photo is used only to make the picture shown to you on that site.
        </p>

        <h2>6. Deleting your photos</h2>
        <p>
          Delete your photos, and remove saved looks, at any time. To delete everything, ask us to delete your
          account through the <Link href="/contact?topic=privacy">contact form</Link>.
        </p>

        <h2>7. Photos of other people</h2>
        <p>
          Only upload photos of yourself, or of someone who has given you permission. Photos of children may be uploaded only by their
          parent or guardian.
        </p>

        <p className="!mt-10">
          See also our <Link href="/privacy">privacy policy</Link> and <Link href="/terms">terms of use</Link>.
        </p>
      </LegalBody>
    </ContentPage>
  );
}
