"use client";

import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { TagInput } from "@/components/ui/TagInput";
import { ApiError, resolveMediaUrl } from "@/lib/api/client";
import { wardrobe as wardrobeApi } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";
import type { WardrobeItem } from "@/lib/api/types";

export function WardrobePage() {
  const router = useRouter();
  const { user, isLoading: sessionLoading } = useSession();
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    if (!sessionLoading && !user) router.replace("/sign-in?next=/wardrobe");
  }, [sessionLoading, user, router]);

  const itemsQuery = useQuery({ queryKey: ["wardrobe"], queryFn: wardrobeApi.list, enabled: !!user });

  if (sessionLoading || !user) {
    return (
      <section className="mx-auto w-[min(1180px,calc(100%-42px))] py-24 text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
      </section>
    );
  }

  return (
    <section className="mx-auto w-[min(1180px,calc(100%-42px))] py-14 md:py-20">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-[clamp(26px,4vw,40px)] leading-tight text-ink">
            My <em>wardrobe</em>
          </h1>
          <p className="mt-3 max-w-lg text-[15px] leading-relaxed text-muted">
            Catalog what you already own, then ask the AI stylist to build an outfit around it.
          </p>
        </div>
        <Button size="md" onClick={() => setAdding((v) => !v)}>
          {adding ? "Cancel" : "+ Add item"}
        </Button>
      </div>

      {adding && (
        <div className="mt-8">
          <AddWardrobeItemForm onAdded={() => setAdding(false)} />
        </div>
      )}

      <div className="mt-10">
        {itemsQuery.isLoading && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="aspect-[3/4] animate-pulse rounded-[18px] bg-paper-2" />
            ))}
          </div>
        )}

        {itemsQuery.data && itemsQuery.data.length === 0 && !adding && (
          <div className="rounded-[22px] border border-dashed border-line p-10 text-center">
            <p className="text-[14px] text-muted">Nothing in your wardrobe yet.</p>
          </div>
        )}

        {itemsQuery.data && itemsQuery.data.length > 0 && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {itemsQuery.data.map((item) => (
              <WardrobeItemCard key={item.id} item={item} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function AddWardrobeItemForm({ onAdded }: { onAdded: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [color, setColor] = useState("");
  const [brand, setBrand] = useState("");
  const [styleTags, setStyleTags] = useState<string[]>([]);

  const create = useMutation({
    mutationFn: () =>
      wardrobeApi.create({
        name: name.trim(),
        category: category.trim() || undefined,
        color: color.trim() || undefined,
        brand: brand.trim() || undefined,
        style_tags: styleTags.length ? styleTags : undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["wardrobe"] });
      onAdded();
    },
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim() || create.isPending) return;
    create.mutate();
  };

  return (
    <form onSubmit={onSubmit} className="grid gap-4 rounded-[22px] border border-line bg-surface p-6 sm:grid-cols-2">
      <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Black Trousers" required />
      <Input label="Category" value={category} onChange={(e) => setCategory(e.target.value)} placeholder="Bottoms" />
      <Input label="Color" value={color} onChange={(e) => setColor(e.target.value)} placeholder="Black" />
      <Input label="Brand" value={brand} onChange={(e) => setBrand(e.target.value)} placeholder="Levi's" />
      <div className="sm:col-span-2">
        <span className="mb-1.5 block text-[13px] font-medium text-ink-soft">Style tags</span>
        <TagInput values={styleTags} onChange={setStyleTags} placeholder="e.g. formal, casual — press Enter" />
      </div>

      {create.isError && (
        <p role="alert" className="text-[13px] text-[#a4553f] sm:col-span-2">
          {create.error instanceof ApiError ? create.error.detail : "Couldn't add this item."}
        </p>
      )}

      <Button type="submit" size="md" className="sm:col-span-2" disabled={!name.trim() || create.isPending}>
        {create.isPending ? "Adding…" : "Add to wardrobe"}
      </Button>
    </form>
  );
}

function WardrobeItemCard({ item }: { item: WardrobeItem }) {
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const remove = useMutation({
    mutationFn: () => wardrobeApi.remove(item.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wardrobe"] }),
  });

  const uploadPhoto = useMutation({
    mutationFn: (file: File) => wardrobeApi.uploadPhoto(item.id, file),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["wardrobe"] }),
  });

  const image = resolveMediaUrl(item.image_url);

  return (
    <div className="group overflow-hidden rounded-[18px] border border-line bg-surface">
      <button
        type="button"
        onClick={() => fileInputRef.current?.click()}
        className="relative block aspect-[3/4] w-full bg-paper-2"
      >
        {image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={image} alt={item.name} className="h-full w-full object-cover object-top" />
        ) : (
          <span className="absolute inset-0 grid place-items-center text-[12px] text-faint">
            {uploadPhoto.isPending ? "Uploading…" : "+ Add photo"}
          </span>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) uploadPhoto.mutate(file);
            e.target.value = "";
          }}
        />
      </button>
      <div className="p-2.5">
        <p className="truncate text-[12.5px] font-semibold text-ink">{item.name}</p>
        <p className="mt-0.5 truncate text-[11px] text-muted">
          {[item.category, item.color].filter(Boolean).join(" · ") || " "}
        </p>
        <button
          type="button"
          onClick={() => remove.mutate()}
          disabled={remove.isPending}
          className="mt-1.5 text-[11px] text-faint hover:text-[#a4553f]"
        >
          {remove.isPending ? "Removing…" : "Remove"}
        </button>
      </div>
    </div>
  );
}
