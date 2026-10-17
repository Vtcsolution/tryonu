"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { PostCard } from "@/components/community/PostCard";
import { Button } from "@/components/ui/Button";
import { community } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";

/** /community/post/<id>: one look with its comments open. */
export function PostDetail({ id }: { id: string }) {
  const router = useRouter();
  const { user, isLoading } = useSession();
  useEffect(() => {
    if (!isLoading && !user) router.replace(`/sign-in?next=${encodeURIComponent(`/community/post/${id}`)}`);
  }, [isLoading, user, router, id]);
  const post = useQuery({ queryKey: ["community", "post", id], queryFn: () => community.post(id), enabled: !!user, retry: false });
  if (!user || post.isLoading) {
    return <div className="mx-auto my-24 h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />;
  }
  if (!post.data) {
    return (
      <section className="tu-container py-20 text-center">
        <p className="font-display text-[26px] text-ink">This post isn&apos;t available</p>
        <Button href="/community" size="md" className="mt-5">Back to the community</Button>
      </section>
    );
  }
  return (
    <section className="tu-container py-8 md:py-12">
      <div className="mx-auto max-w-[640px]">
        <Button href="/community" size="sm" variant="outline">← Community</Button>
        <div className="mt-4">
          <PostCard post={post.data} openComments onRemoved={() => router.replace("/community")} />
        </div>
      </div>
    </section>
  );
}

/** /community/me: straight to my own profile. */
export function MyProfileRedirect() {
  const router = useRouter();
  const { user, isLoading } = useSession();
  const me = useQuery({ queryKey: ["community", "me"], queryFn: community.me, enabled: !!user });
  useEffect(() => {
    if (!isLoading && !user) router.replace("/sign-in?next=/community/me");
    if (me.data) router.replace(`/u/${me.data.handle}`);
  }, [isLoading, user, me.data, router]);
  return <div className="mx-auto my-24 h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />;
}
