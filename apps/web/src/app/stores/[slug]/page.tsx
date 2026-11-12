import { permanentRedirect } from "next/navigation";

// stores live at tryonu.app/<store> now; old links keep working
export default async function OldStorePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  permanentRedirect(`/${encodeURIComponent(slug)}`);
}
