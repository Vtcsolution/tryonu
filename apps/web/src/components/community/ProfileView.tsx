"use client";

import Link from "next/link";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Medal, PLACE } from "@/components/community/extras";
import { Avatar, ThumbIcon } from "@/components/community/parts";
import { Button } from "@/components/ui/Button";
import { ApiError, mediaThumb, resolveMediaUrl } from "@/lib/api/client";
import { community, type CommunityProfile } from "@/lib/api/endpoints";
import { SESSION_QUERY_KEY, useSession } from "@/lib/auth/useSession";

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
    <section className="tu-container pb-10 pt-3 lg:py-12">
      <div className="mx-auto max-w-[1000px]">
        <div className="flex flex-wrap items-center gap-5 rounded-[24px] border border-line bg-surface p-5 md:p-7">
          {p.is_me ? (
            <AvatarPicker profile={p} onChanged={(np) => qc.setQueryData(key, np)} />
          ) : (
            <Avatar name={p.name} handle={p.handle} url={p.avatar_url} size={84} />
          )}
          <div className="min-w-0 flex-1">
            <h1 className="truncate font-display text-[28px] leading-tight text-ink">{p.name || p.handle}</h1>
            <p className="text-[15px] text-muted">@{p.handle}</p>
            {p.bio && <p className="mt-2 max-w-xl whitespace-pre-wrap text-[15.5px] text-ink-soft">{p.bio}</p>}
            <div className="mt-3 flex gap-5 text-[15px] text-ink-soft">
              <span><b className="text-ink">{p.posts}</b> looks</span>
              <span><b className="text-ink">{p.followers}</b> followers</span>
              <span><b className="text-ink">{p.following}</b> following</span>
            </div>
            {p.trophies && p.trophies.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {p.trophies.map((t) => (
                  <Link
                    key={t.challenge_id}
                    href={`/community/challenges/${t.challenge_id}`}
                    className="inline-flex items-center gap-1.5 rounded-full border border-[#c9a13b]/50 bg-[#c9a13b]/[0.08] px-3 py-1 text-[13px] font-semibold text-[#8a6d1f] hover:border-[#c9a13b]"
                  >
                    <Medal place={t.place} size={18} /> {PLACE[t.place]} place · {t.title}
                  </Link>
                ))}
              </div>
            )}
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
              {p.followed_by_me ? "Following" : "Follow"}
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
              {post.media_kind === "video" ? (
                <>
                  {post.poster_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={mediaThumb(post.poster_url, 400)} alt={post.caption || "A video"} loading="lazy" className="h-full w-full object-cover" />
                  ) : (
                    <video src={resolveMediaUrl(post.video_url)} muted playsInline preload="metadata" className="h-full w-full object-cover" />
                  )}
                  <span aria-hidden="true" className="absolute right-2 top-2 grid h-7 w-7 place-items-center rounded-full bg-black/55 text-white">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
                  </span>
                </>
              ) : (
                post.image_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={mediaThumb(post.image_url, 400)} alt={post.caption || "A look"} loading="lazy" className="h-full w-full object-cover object-top transition-transform group-hover:scale-[1.02]" />
                )
              )}
              <span className="absolute bottom-2 left-2 flex items-center gap-3 rounded-full bg-black/55 px-2.5 py-1 text-[12.5px] font-semibold text-white">
                <span className="flex items-center gap-1">
                  <ThumbIcon filled size={13} />
                  {post.like_count}
                </span>
                <span className="flex items-center gap-1">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M4 5.5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9.5L5 21v-3.5H4a1 1 0 0 1-1-1v-10a1 1 0 0 1 1-1z" /></svg>
                  {post.comment_count}
                </span>
                <span className="sr-only">likes and comments</span>
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

/** My own profile picture: tap to upload or change it; remove it from the small menu. */
function AvatarPicker({ profile, onChanged }: { profile: CommunityProfile; onChanged: (p: CommunityProfile) => void }) {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const done = (p: CommunityProfile) => {
    setError(null);
    onChanged(p);
    // the account button and every post of mine show the new picture
    qc.invalidateQueries({ queryKey: SESSION_QUERY_KEY });
    qc.invalidateQueries({ queryKey: ["community"] });
  };
  const upload = useMutation({
    mutationFn: (file: File) => community.uploadAvatar(file),
    onSuccess: done,
    onError: (err) => setError(err instanceof ApiError ? err.detail : "Couldn't upload that photo."),
  });
  const remove = useMutation({ mutationFn: community.removeAvatar, onSuccess: done });
  return (
    <div className="flex flex-col items-center gap-1.5">
      <label className="group relative cursor-pointer" title="Change profile picture">
        <input
          type="file"
          accept="image/*"
          className="sr-only"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) upload.mutate(file);
            e.target.value = "";
          }}
        />
        <Avatar name={profile.name} handle={profile.handle} url={profile.avatar_url} size={84} />
        <span className="absolute inset-0 grid place-items-center rounded-full bg-black/45 text-[12.5px] font-semibold text-white opacity-0 transition-opacity group-hover:opacity-100">
          {upload.isPending ? "Uploading…" : "Change"}
        </span>
        <span aria-hidden="true" className="absolute -bottom-0.5 -right-0.5 grid h-8 w-8 place-items-center rounded-full border-2 border-surface bg-sage text-white">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"><path d="M4 8h3l1.5-2h7L17 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z" /><circle cx="12" cy="13" r="3.5" /></svg>
        </span>
        <span className="sr-only">Upload a profile picture</span>
      </label>
      {upload.isPending && <span className="text-[12.5px] text-muted">Uploading…</span>}
      {profile.avatar_url && !upload.isPending && (
        <button type="button" onClick={() => remove.mutate()} disabled={remove.isPending} className="text-[12.5px] text-muted hover:text-[#a4553f]">
          Remove photo
        </button>
      )}
      {error && <span className="max-w-[140px] text-center text-[12.5px] text-[#a4553f]">{error}</span>}
    </div>
  );
}
