import { JsonLd } from "@/components/seo/JsonLd";
import { appJsonLd } from "@/components/seo/appJsonLd";
import { TopicPage, topicMetadata } from "@/components/seo/TopicPage";

export const metadata = topicMetadata("virtual-try-on-app");

export default async function Page() {
  return (
    <>
      <JsonLd data={await appJsonLd()} />
      <TopicPage slug="virtual-try-on-app" />
    </>
  );
}
