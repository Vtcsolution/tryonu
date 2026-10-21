"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Avatar } from "@/components/community/parts";
import { AnnouncementsAdmin } from "./AnnouncementsAdmin";
import { ChallengesAdmin } from "./ChallengesAdmin";
import { resolveMediaUrl } from "@/lib/api/client";
import { adminCommunity, type AdminCommunityComment } from "@/lib/api/endpoints";
import {
  Badge,
  ErrorNote,
  Pager,
  SectionHeader,
  SmallButton,
  StatTile,
  Table,
  TableSkeleton,
  errorText,
  inputClass,
  when,
} from "./ui";

type View = "overview" | "members" | "comments" | "posts" | "challenges" | "announcements" | "reports";

/** Everything members do in the community: who takes part and how much,
 * every comment and post, and the reports to review. */
export function CommunityTab() {
  const [view, setView] = useState<View>("overview");
  const [member, setMember] = useState(""); // a member's @handle, to see only what they did
  const open = (v: View, handle = "") => {
    setMember(handle);
    setView(v);
  };
  const stats = useQuery({ queryKey: ["admin", "community", "stats"], queryFn: adminCommunity.stats });
  const views: [View, string][] = [
    ["overview", "Overview"],
    ["members", "Members"],
    ["comments", "Comments"],
    ["posts", "Posts"],
    ["challenges", "Challenges"],
    ["announcements", "Announcements"],
    ["reports", stats.data?.open_reports ? `Reports (${stats.data.open_reports})` : "Reports"],
  ];
  return (
    <div className="space-y-5">
      <div role="tablist" aria-label="Community" className="flex flex-wrap gap-2">
        {views.map(([id, label]) => (
          <SmallButton key={id} tone={view === id ? "primary" : undefined} onClick={() => open(id)}>
            {label}
          </SmallButton>
        ))}
      </div>
      {member && (view === "comments" || view === "posts") && (
        <p className="flex items-center gap-2 text-[14px] text-ink-soft">
          Showing only <b className="text-ink">@{member}</b>
          <SmallButton onClick={() => setMember("")}>Show everyone</SmallButton>
        </p>
      )}
      {view === "overview" && <Overview onOpen={open} />}
      {view === "members" && <Members onOpen={open} />}
      {view === "comments" && <CommentsList member={member} />}
      {view === "posts" && <PostsList member={member} />}
      {view === "challenges" && <ChallengesAdmin />}
      {view === "announcements" && <AnnouncementsAdmin />}
      {view === "reports" && <Reports />}
    </div>
  );
}

function Overview({ onOpen }: { onOpen: (v: View, handle?: string) => void }) {
  const stats = useQuery({ queryKey: ["admin", "community", "stats"], queryFn: adminCommunity.stats });
  const top = useQuery({ queryKey: ["admin", "community", "members", "", "engaged", 0], queryFn: () => adminCommunity.members({}) });
  const latest = useQuery({ queryKey: ["admin", "community", "comments", "", "", "all", 0], queryFn: () => adminCommunity.comments({}) });
  const s = stats.data;
  return (
    <div className="space-y-6">
      <SectionHeader title="Community at a glance" hint="All time, with the last 7 days in brackets." />
      {stats.isError && <ErrorNote>{errorText(stats.error)}</ErrorNote>}
      {s && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatTile label="Members" value={`${s.members} (${s.active_7d} active)`} />
          <StatTile label="Posts" value={`${s.posts} (+${s.posts_7d})`} />
          <StatTile label="Comments" value={`${s.comments} (+${s.comments_7d})`} />
          <StatTile label="Post likes" value={`${s.likes} (+${s.likes_7d})`} />
          <StatTile label="Comment likes" value={s.comment_likes} />
          <StatTile label="Follows" value={s.follows} />
          <StatTile label="Outside links removed" value={s.links_removed} tone={s.links_removed ? "warn" : undefined} />
          <StatTile label="Open reports" value={s.open_reports} tone={s.open_reports ? "warn" : undefined} />
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-2">
        <div>
          <SectionHeader title="Most engaged members">
            <SmallButton onClick={() => onOpen("members")}>All members →</SmallButton>
          </SectionHeader>
          {top.isLoading && <TableSkeleton />}
          <div className="space-y-2">
            {top.data?.rows.slice(0, 6).map((m) => (
              <div key={m.user_id} className="flex items-center gap-3 rounded-[14px] border border-line bg-surface p-3">
                <Avatar name={m.name} handle={m.handle} url={m.avatar_url} size={36} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[14.5px] font-semibold text-ink">
                    {m.name || `@${m.handle}`} <span className="font-normal text-muted">@{m.handle}</span>
                  </p>
                  <p className="text-[13px] text-muted">
                    Posts {m.posts} · Comments {m.comments} · Likes given {m.likes_given} · Likes received {m.likes_received}
                  </p>
                </div>
                <SmallButton onClick={() => onOpen("comments", m.handle)}>Comments</SmallButton>
              </div>
            ))}
            {top.data && top.data.rows.length === 0 && <p className="text-[14px] text-muted">No members yet.</p>}
          </div>
        </div>
        <div>
          <SectionHeader title="Latest comments">
            <SmallButton onClick={() => onOpen("comments")}>All comments →</SmallButton>
          </SectionHeader>
          {latest.isLoading && <TableSkeleton />}
          <div className="space-y-2">
            {latest.data?.rows.slice(0, 6).map((c) => <CommentRow key={c.id} c={c} compact />)}
            {latest.data && latest.data.rows.length === 0 && <p className="text-[14px] text-muted">No comments yet.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

function useDebounced(value: string, ms = 350) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function Members({ onOpen }: { onOpen: (v: View, handle?: string) => void }) {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<"engaged" | "newest" | "blocked">("engaged");
  const [offset, setOffset] = useState(0);
  const search = useDebounced(q);
  const list = useQuery({
    queryKey: ["admin", "community", "members", search, sort, offset],
    queryFn: () => adminCommunity.members({ q: search, sort, offset }),
  });
  const block = useMutation({
    mutationFn: ({ id, on }: { id: string; on: boolean }) => (on ? adminCommunity.block(id) : adminCommunity.unblock(id)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "community"] }),
  });
  return (
    <div>
      <SectionHeader title="Members" hint="Everyone who has used the community, and how much they take part.">
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOffset(0);
          }}
          placeholder="Search name, @username, email"
          className={`${inputClass} w-64`}
        />
        {(["engaged", "newest", "blocked"] as const).map((s) => (
          <SmallButton
            key={s}
            tone={sort === s ? "primary" : undefined}
            onClick={() => {
              setSort(s);
              setOffset(0);
            }}
          >
            {s === "engaged" ? "Most engaged" : s === "newest" ? "Newest" : "Blocked"}
          </SmallButton>
        ))}
      </SectionHeader>
      {list.isError && <ErrorNote>{errorText(list.error)}</ErrorNote>}
      {list.isLoading ? (
        <TableSkeleton />
      ) : (
        <Table
          columns={["Member", "Posts", "Comments", "Likes given", "Likes received", "Followers", "Links removed", "Last active", ""]}
          empty="No members found."
          rows={(list.data?.rows ?? []).map((m) => [
            <div key="m" className="flex min-w-[220px] items-center gap-2.5">
              <Avatar name={m.name} handle={m.handle} url={m.avatar_url} size={32} />
              <div className="min-w-0">
                <Link href={`/u/${m.handle}`} target="_blank" className="block truncate font-semibold text-ink hover:underline">
                  {m.name || `@${m.handle}`}
                </Link>
                <span className="block truncate text-[12.5px] text-muted">
                  @{m.handle} · {m.email}
                </span>
              </div>
              {m.blocked_at && <Badge tone="bad">Blocked</Badge>}
            </div>,
            m.posts,
            m.comments,
            m.likes_given,
            m.likes_received,
            m.followers,
            m.links_removed ? <Badge tone="warn">{m.links_removed}</Badge> : 0,
            <span key="t" className="whitespace-nowrap text-[13px] text-muted">{when(m.last_active_at)}</span>,
            <div key="a" className="flex gap-1.5 whitespace-nowrap">
              <SmallButton onClick={() => onOpen("comments", m.handle)}>Comments</SmallButton>
              <SmallButton onClick={() => onOpen("posts", m.handle)}>Posts</SmallButton>
              {m.blocked_at ? (
                <SmallButton disabled={block.isPending} onClick={() => block.mutate({ id: m.user_id, on: false })}>Unblock</SmallButton>
              ) : (
                <SmallButton
                  tone="danger"
                  disabled={block.isPending}
                  onClick={() => window.confirm(`Block @${m.handle} from the community? Their posts and comments disappear.`) && block.mutate({ id: m.user_id, on: true })}
                >
                  Block
                </SmallButton>
              )}
            </div>,
          ])}
        />
      )}
      {block.isError && <ErrorNote>{errorText(block.error)}</ErrorNote>}
      <Pager offset={offset} total={list.data?.total ?? 0} onChange={setOffset} />
    </div>
  );
}

function CommentsList({ member }: { member: string }) {
  const [q, setQ] = useState("");
  const [show, setShow] = useState<"all" | "hidden" | "links">("all");
  const [offset, setOffset] = useState(0);
  const search = useDebounced(q);
  useEffect(() => setOffset(0), [member]);
  const list = useQuery({
    queryKey: ["admin", "community", "comments", search, member, show, offset],
    queryFn: () => adminCommunity.comments({ q: search, member, show, offset }),
  });
  return (
    <div>
      <SectionHeader title="Comments" hint="Every comment and reply, newest first.">
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOffset(0);
          }}
          placeholder="Search the words"
          className={`${inputClass} w-56`}
        />
        {(["all", "links", "hidden"] as const).map((s) => (
          <SmallButton
            key={s}
            tone={show === s ? "primary" : undefined}
            onClick={() => {
              setShow(s);
              setOffset(0);
            }}
          >
            {s === "all" ? "All" : s === "links" ? "Links removed" : "Hidden"}
          </SmallButton>
        ))}
      </SectionHeader>
      {list.isError && <ErrorNote>{errorText(list.error)}</ErrorNote>}
      {list.isLoading && <TableSkeleton />}
      <div className="space-y-2">
        {list.data?.rows.map((c) => <CommentRow key={c.id} c={c} />)}
        {list.data && list.data.rows.length === 0 && (
          <p className="rounded-[16px] border border-dashed border-line p-6 text-center text-[14px] text-muted">No comments found.</p>
        )}
      </div>
      <Pager offset={offset} total={list.data?.total ?? 0} onChange={setOffset} />
    </div>
  );
}

function CommentRow({ c, compact = false }: { c: AdminCommunityComment; compact?: boolean }) {
  const qc = useQueryClient();
  const hide = useMutation({
    mutationFn: (hidden: boolean) => adminCommunity.hideComment(c.id, hidden),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "community"] }),
  });
  return (
    <article className={`flex gap-3 rounded-[14px] border bg-surface p-3 ${c.hidden ? "border-[#c0503a]/30 opacity-75" : "border-line"}`}>
      <Avatar name={c.author.name} handle={c.author.handle} url={c.author.avatar_url} size={34} />
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13.5px]">
          <b className="text-ink">@{c.author.handle}</b>
          {!compact && <span className="text-muted">{c.author_email}</span>}
          <span className="text-faint">{when(c.created_at)}</span>
          {c.reply_to && <Badge>Reply to @{c.reply_to}</Badge>}
          {c.links_removed > 0 && <Badge tone="warn">{c.links_removed} link{c.links_removed > 1 ? "s" : ""} removed</Badge>}
          {c.hidden && <Badge tone="bad">Hidden</Badge>}
          {c.like_count > 0 && <span className="text-muted">{c.like_count} likes</span>}
        </p>
        {c.body && <p className={`mt-1 whitespace-pre-wrap break-words text-[14.5px] text-ink ${compact ? "line-clamp-2" : ""}`}>{c.body}</p>}
        {(c.image_url || c.look_image_url) && (
          <div className="mt-2 flex gap-2">
            {c.image_url && (
              <a href={resolveMediaUrl(c.image_url)} target="_blank" rel="noopener">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={resolveMediaUrl(c.image_url)} alt="Photo in the comment" className="h-20 w-20 rounded-lg object-cover" />
              </a>
            )}
            {c.look_image_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={resolveMediaUrl(c.look_image_url)} alt="Look in the comment" className="h-20 w-16 rounded-lg object-cover object-top" title="A look" />
            )}
          </div>
        )}
        <p className="mt-1 text-[12.5px] text-muted">
          On{" "}
          <Link href={`/community/post/${c.post_id}`} target="_blank" className="font-semibold text-ink-soft hover:underline">
            {c.post_author_handle ? `@${c.post_author_handle}'s post` : "a post"}
          </Link>
          {c.post_caption ? `: “${c.post_caption.slice(0, 60)}${c.post_caption.length > 60 ? "…" : ""}”` : ""}
        </p>
      </div>
      {!compact && (
        <div className="shrink-0">
          <SmallButton tone={c.hidden ? undefined : "danger"} disabled={hide.isPending} onClick={() => hide.mutate(!c.hidden)}>
            {c.hidden ? "Show again" : "Hide"}
          </SmallButton>
        </div>
      )}
    </article>
  );
}

function PostsList({ member }: { member: string }) {
  const qc = useQueryClient();
  const [sort, setSort] = useState<"newest" | "engaged" | "hidden">("newest");
  const [offset, setOffset] = useState(0);
  useEffect(() => setOffset(0), [member]);
  const list = useQuery({
    queryKey: ["admin", "community", "posts", member, sort, offset],
    queryFn: () => adminCommunity.posts({ member, sort, offset }),
  });
  const hide = useMutation({
    mutationFn: ({ id, hidden }: { id: string; hidden: boolean }) => adminCommunity.hidePost(id, hidden),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "community"] }),
  });
  return (
    <div>
      <SectionHeader title="Posts" hint="Every post, hidden ones too, with its likes and comments.">
        {(["newest", "engaged", "hidden"] as const).map((s) => (
          <SmallButton
            key={s}
            tone={sort === s ? "primary" : undefined}
            onClick={() => {
              setSort(s);
              setOffset(0);
            }}
          >
            {s === "newest" ? "Newest" : s === "engaged" ? "Most engaged" : "Hidden"}
          </SmallButton>
        ))}
      </SectionHeader>
      {list.isError && <ErrorNote>{errorText(list.error)}</ErrorNote>}
      {list.isLoading && <TableSkeleton />}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {list.data?.rows.map((p) => (
          <article key={p.id} className={`overflow-hidden rounded-[16px] border bg-surface ${p.hidden ? "border-[#c0503a]/40" : "border-line"}`}>
            <Link href={`/community/post/${p.id}`} target="_blank" className="relative block aspect-[3/4] bg-paper-2">
              {p.media_kind === "video" && p.video_url && !p.image_url ? (
                <video src={resolveMediaUrl(p.video_url)} muted playsInline preload="metadata" className="h-full w-full object-cover" />
              ) : (
                p.image_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={resolveMediaUrl(p.image_url)} alt={p.caption || "A post"} loading="lazy" className="h-full w-full object-cover object-top" />
                )
              )}
              <span className="absolute left-2 top-2 flex gap-1">
                {p.media_kind !== "tryon" && <Badge>{p.media_kind === "video" ? "Video" : "Photo"}</Badge>}
                {p.hidden && <Badge tone="bad">Hidden</Badge>}
              </span>
            </Link>
            <div className="p-2.5">
              <p className="truncate text-[13.5px] font-semibold text-ink">@{p.author.handle}</p>
              {p.caption && <p className="line-clamp-2 text-[13px] text-ink-soft">{p.caption}</p>}
              <p className="mt-1 text-[12.5px] text-muted">
                {p.like_count} likes · {p.comment_count} comments
                {p.links_removed > 0 ? ` · ${p.links_removed} link${p.links_removed > 1 ? "s" : ""} removed` : ""}
              </p>
              <p className="text-[12px] text-faint">{when(p.created_at)}</p>
              <div className="mt-2">
                <SmallButton tone={p.hidden ? undefined : "danger"} disabled={hide.isPending} onClick={() => hide.mutate({ id: p.id, hidden: !p.hidden })}>
                  {p.hidden ? "Show again" : "Hide"}
                </SmallButton>
              </div>
            </div>
          </article>
        ))}
      </div>
      {list.data && list.data.rows.length === 0 && (
        <p className="rounded-[16px] border border-dashed border-line p-6 text-center text-[14px] text-muted">No posts found.</p>
      )}
      <Pager offset={offset} total={list.data?.total ?? 0} onChange={setOffset} pageSize={24} />
    </div>
  );
}

/** Reported community posts and comments: hide them, block the member, or dismiss. */
function Reports() {
  const qc = useQueryClient();
  const [show, setShow] = useState<"open" | "all">("open");
  const list = useQuery({ queryKey: ["admin", "community", "reports", show], queryFn: () => adminCommunity.reports(show) });
  const act = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "hide" | "dismiss" | "ban" }) => adminCommunity.resolve(id, action),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "community"] }),
  });
  return (
    <div className="space-y-5">
      <SectionHeader
        title="Community reports"
        hint="Posts and comments members reported. Hide: it disappears. Block member: they can't post or comment, and their posts and comments disappear. Dismiss: nothing wrong."
      >
        <div className="flex gap-2">
          <SmallButton tone={show === "open" ? "primary" : undefined} onClick={() => setShow("open")}>Open</SmallButton>
          <SmallButton tone={show === "all" ? "primary" : undefined} onClick={() => setShow("all")}>All</SmallButton>
        </div>
      </SectionHeader>
      {list.isError && <ErrorNote>{errorText(list.error)}</ErrorNote>}
      {list.isLoading && <TableSkeleton />}
      {list.data && list.data.length === 0 && (
        <p className="rounded-[16px] border border-dashed border-line p-8 text-center text-[15px] text-muted">
          {show === "open" ? "Nothing to review." : "No reports yet."}
        </p>
      )}
      <div className="space-y-3">
        {list.data?.map((r) => (
          <article key={r.id} className="flex flex-wrap gap-4 rounded-[18px] border border-line bg-surface p-4">
            {r.video_url ? (
              <video src={resolveMediaUrl(r.video_url)} controls playsInline preload="metadata" className="h-40 w-28 shrink-0 rounded-xl bg-black object-cover" />
            ) : (
              r.image_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={resolveMediaUrl(r.image_url)} alt="" className="h-32 w-24 shrink-0 rounded-xl bg-paper-2 object-cover object-top" />
              )
            )}
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge>{r.kind === "post" ? "Post" : "Comment"}</Badge>
                {r.hidden ? <Badge tone="bad">Hidden</Badge> : r.resolved_at ? <Badge tone="good">Done</Badge> : <Badge tone="warn">Open</Badge>}
                <span className="text-[13px] text-faint">{when(r.created_at)}</span>
              </div>
              <p className="mt-2 text-[14.5px] text-ink">
                By <b>@{r.author_handle ?? "?"}</b> <span className="text-muted">({r.author_email})</span>
              </p>
              {r.text && <p className="mt-1 whitespace-pre-wrap rounded-lg bg-paper-2 px-3 py-2 text-[14.5px] text-ink-soft">{r.text}</p>}
              <p className="mt-2 text-[13.5px] text-muted">
                Reported by {r.reporter_email}: “{r.reason}”
              </p>
              {!r.resolved_at && (
                <div className="mt-3 flex flex-wrap gap-2">
                  <SmallButton tone="danger" disabled={act.isPending} onClick={() => act.mutate({ id: r.id, action: "hide" })}>Hide</SmallButton>
                  <SmallButton tone="danger" disabled={act.isPending} onClick={() => act.mutate({ id: r.id, action: "ban" })}>Hide + block member</SmallButton>
                  <SmallButton disabled={act.isPending} onClick={() => act.mutate({ id: r.id, action: "dismiss" })}>Dismiss</SmallButton>
                </div>
              )}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
