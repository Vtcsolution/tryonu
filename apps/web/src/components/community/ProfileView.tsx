"use client";

import Link from "next/link";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Avatar } from "@/components/community/PostCard";
import { Button } from "@/components/ui/Button";
import { ApiError, resolveMediaUrl } from "@/lib/api/client";
import { community } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";

/** /u/<handle>: a member's looks, followers and following, Follow / Edit profile. */
export function ProfileView({ handle }: { handle: string }) {
  const router = useRouter();
  const qc = useQueryClient();
  const { user, isLoading } = useSession();
  useEffect(() => {
    if (!isLoading && !user) router.replace(`/sign-in?next=${encodeURIComponent(`/u/${handle}`)}`);
  }, [isLoading, user, router, handle]);
  const key = ["community", "profile", handle];
  const profile = useQuery({ queryKey: key, queryFn: () => community.profile(handle), enabled: !!user, retry: false });
  const posts = useInfiniteQuery({
    queryKey: ["community", "profile-posts", handle],
    queryFn: ({ pageParam }) => community.profilePosts(handle, pageParam),
    initialPageParam: 0,
    getNextPageParam: (last) => last.next_offset ?? undefined,
    enabled: !!user && profile.isSuccess,
  });
  const toggle = useMutation({
    mutationFn: () => (profile.data?.followed_by_me ? community.unfollow(handle) : community.follow(handle)),
    onSuccess: (p) => qc.setQueryData(key, p),
  });
  const [editing, setEditing] = useState(false);

  if (!user || profile.isLoading) {
    return <div className="mx-auto my-24 h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />;
  }
  if (profile.isError || !profile.data) {
    return (
      <section className="tu-container py-20 text-center">
        <p className="font-display text-[26px] text-ink">This member isn&apos;t in the community</p>
        <Button href="/community" size="md" className="mt-5">Back to the community</Button>
      </section>
    );
  }
  const p = profile.data;
  const items = posts.data?.pages.flatMap((pg) => pg.posts) ?? [];
  return (
    <section className="tu-container py-8 md:py-12">
      <div className="mx-auto max-w-[1000px]">
        <div className="flex flex-wrap items-center gap-5 rounded-[24px] border border-line bg-surface p-5 md:p-7">
          <Avatar name={p.name} handle={p.handle} url={p.avatar_url} size={84} />
          <div className="min-w-0 flex-1">
            <h1 className="truncate font-display text-[28px] leading-tight text-ink">{p.name || p.handle}</h1>
            <p className="text-[15px] text-muted">@{p.handle}</p>
            {p.bio && <p className="mt-2 max-w-xl whitespace-pre-wrap text-[15.5px] text-ink-soft">{p.bio}</p>}
            <div className="mt-3 flex gap-5 text-[15px] text-ink-soft">
              <span><b className="text-ink">{p.posts}</b> looks</span>
              <span><b className="text-ink">{p.followers}</b> followers</span>
              <span><b className="text-ink">{p.following}</b> following</span>
            </div>
          </div>
          {p.is_me ? (
            <button type="button" onClick={() => setEditing(true)} className="tu-press min-h-[44px] rounded-full border border-line-strong px-5 text-[15px] font-semibold text-ink">
              Edit profile
            </button>
          ) : (
            <button
              type="button"
              onClick={() => toggle.mutate()}
              disabled={toggle.isPending}
              className={`tu-press min-h-[44px] rounded-full px-6 text-[15px] font-semibold ${
                p.followed_by_me ? "border border-line-strong text-ink" : "bg-ink text-surface"
              }`}
            >
              {p.followed_by_me ? "Following ✓" : "Follow"}
            </button>
          )}
        </div>

        {editing && <EditProfile handle={p.handle} bio={p.bio} onDone={(newHandle) => {
          setEditing(false);
          if (newHandle !== p.handle) router.replace(`/u/${newHandle}`);
          else qc.invalidateQueries({ queryKey: key });
        }} />}

        <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {items.map((post) => (
            <Link key={post.id} href={`/community/post/${post.id}`} className="group relative block aspect-[3/4] overflow-hidden rounded-[16px] bg-paper-2">
              {post.image_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={resolveMediaUrl(post.image_url)} alt={post.caption || "A look"} loading="lazy" className="h-full w-full object-cover object-top transition-transform group-hover:scale-[1.02]" />
              )}
              <span className="absolute bottom-2 left-2 rounded-full bg-black/55 px-2.5 py-1 text-[12.5px] font-semibold text-white">
                ♥ {post.like_count} · 💬 {post.comment_count}
              </span>
            </Link>
          ))}
        </div>
        {!posts.isLoading && items.length === 0 && (
          <p className="mt-8 rounded-[20px] border border-dashed border-line p-10 text-center text-[16px] text-muted">
            {p.is_me ? "You haven't posted a look yet. Make a try-on and press “Post to community”." : "No looks posted yet."}
          </p>
        )}
        {posts.hasNextPage && (
          <button type="button" onClick={() => posts.fetchNextPage()} className="tu-press mt-6 min-h-[46px] w-full rounded-full border border-line-strong text-[15px] font-semibold text-ink">
            Show more
          </button>
        )}
      </div>
    </section>
  );
}

function EditProfile({ handle, bio, onDone }: { handle: string; bio: string | null; onDone: (handle: string) => void }) {
  const [h, setH] = useState(handle);
  const [b, setB] = useState(bio ?? "");
  const save = useMutation({ mutationFn: () => community.updateMe({ handle: h, bio: b }), onSuccess: (p) => onDone(p.handle) });
  return (
    <div className="mt-4 rounded-[20px] border border-line bg-surface p-5">
      <label className="block text-[14px] font-semibold text-ink">
        Username
        <div className="mt-1.5 flex items-center rounded-xl border border-line-strong bg-paper px-3">
          <span className="text-muted">@</span>
          <input value={h} onChange={(e) => setH(e.target.value.toLowerCase())} maxLength={30} className="h-11 min-w-0 flex-1 bg-transparent px-1 text-[15px] text-ink outline-none" />
        </div>
      </label>
      <label className="mt-3 block text-[14px] font-semibold text-ink">
        Bio
        <textarea value={b} onChange={(e) => setB(e.target.value)} maxLength={280} rows={3} placeholder="A line about your style" className="mt-1.5 w-full rounded-xl border border-line-strong bg-paper p-3 text-[15px] text-ink" />
      </label>
      {save.isError && <p className="mt-2 text-[14px] text-[#a4553f]">{save.error instanceof ApiError ? save.error.detail : "Couldn't save."}</p>}
      <div className="mt-4 flex gap-3">
        <button type="button" onClick={() => onDone(handle)} className="min-h-[44px] rounded-full border border-line-strong px-5 text-[15px] font-semibold text-ink">Cancel</button>
        <button type="button" disabled={save.isPending} onClick={() => save.mutate()} className="tu-press min-h-[44px] rounded-full bg-sage px-6 text-[15px] font-semibold text-white">
          {save.isPending ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}
