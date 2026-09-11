"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { resolveMediaUrl } from "@/lib/api/client";
import { photos as photosApi } from "@/lib/api/endpoints";
import type { PhotoKind, UserPhoto } from "@/lib/api/types";

const SLOTS: { kind: PhotoKind; label: string }[] = [
  { kind: "front", label: "Front" },
  { kind: "left_45", label: "Left 45°" },
  { kind: "right_45", label: "Right 45°" },
  { kind: "left_side", label: "Left side" },
  { kind: "right_side", label: "Right side" },
  { kind: "full_body", label: "Full body" },
  { kind: "back", label: "Back" },
  { kind: "extra", label: "Extra" },
  { kind: "extra", label: "Extra" },
  { kind: "extra", label: "Extra" },
];

const MAX_PHOTOS = 10;
export const MIN_PHOTOS = 7; // encouraged, not enforced — see isReady below

type SlotUpload = { status: "uploading" | "error"; error?: string };

/**
 * Real fitting-profile uploader: lists existing photos, uploads new ones
 * (per-slot loading + error state), supports delete. A profile is "ready"
 * as soon as the backend has a front or full-body photo (see
 * FittingProfileStatus) — more photos improve render quality but aren't a
 * hard gate.
 */
export function PhotoUploader({
  onPhotosChange,
}: {
  onPhotosChange?: (photos: UserPhoto[], isReady: boolean) => void;
}) {
  const [photos, setPhotos] = useState<UserPhoto[]>([]);
  const [pending, setPending] = useState<Record<number, SlotUpload>>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    photosApi
      .list()
      .then((list) => {
        if (!cancelled) setPhotos(list);
      })
      .catch(() => {
        if (!cancelled) setLoadError("Couldn't load your fitting profile. Try refreshing.");
      })
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const isReady = photos.some((p) => p.kind === "front" || p.kind === "full_body");
    onPhotosChange?.(photos, isReady);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [photos]);

  const uploadAt = async (slotIndex: number, file: File) => {
    const { kind } = SLOTS[slotIndex];
    setPending((p) => ({ ...p, [slotIndex]: { status: "uploading" } }));
    try {
      const photo = await photosApi.upload(file, kind);
      setPhotos((prev) => [...prev.filter((p) => p.id !== photo.id), photo]);
      setPending((p) => {
        const next = { ...p };
        delete next[slotIndex];
        return next;
      });
    } catch (err) {
      setPending((p) => ({
        ...p,
        [slotIndex]: {
          status: "error",
          error: err instanceof Error ? err.message : "Upload failed",
        },
      }));
    }
  };

  const addFiles = (fileList: FileList | null) => {
    if (!fileList) return;
    const emptySlotIndexes = SLOTS.map((_, i) => i).filter((i) => !photoForSlot(i, photos));
    Array.from(fileList)
      .slice(0, emptySlotIndexes.length)
      .forEach((file, i) => uploadAt(emptySlotIndexes[i], file));
  };

  const removePhoto = async (photo: UserPhoto) => {
    const prev = photos;
    setPhotos((p) => p.filter((x) => x.id !== photo.id));
    try {
      await photosApi.remove(photo.id);
    } catch {
      setPhotos(prev); // roll back on failure
    }
  };

  const count = photos.length;
  const pct = Math.min(100, Math.round((count / MIN_PHOTOS) * 100));
  const isReady = photos.some((p) => p.kind === "front" || p.kind === "full_body");

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          addFiles(e.dataTransfer.files);
        }}
        className={`rounded-[22px] border border-dashed px-6 py-10 text-center transition-colors duration-200 ${
          dragging ? "border-sage bg-sage-tint/50" : "border-line-strong bg-paper-2/60"
        }`}
      >
        <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-[18px] border border-line-strong text-2xl text-sage">
          ⇧
        </div>
        <p className="text-[15px] font-semibold text-ink">Drag photos here, or</p>
        <div className="mt-3 flex justify-center">
          <Button
            variant="outline"
            size="sm"
            type="button"
            onClick={() => inputRef.current?.click()}
          >
            Choose photos
          </Button>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={(e) => {
            addFiles(e.target.files);
            e.target.value = "";
          }}
        />
        <p className="mt-3 text-[12px] text-faint">
          JPG, PNG, WEBP or HEIC · up to 12MB each · front or full-body required
        </p>
      </div>

      <div className="mt-5 grid grid-cols-5 gap-2.5">
        {SLOTS.map((slot, i) => {
          const photo = photoForSlot(i, photos);
          const state = pending[i];
          return (
            <div
              key={i}
              className="relative grid aspect-[0.78] place-items-center overflow-hidden rounded-2xl border border-dashed border-line-strong bg-paper-2 p-2 text-center text-[10px] text-faint"
            >
              {photo ? (
                <>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={resolveMediaUrl(photo.url)}
                    alt={slot.label}
                    className="absolute inset-0 h-full w-full animate-[tu-in-scale_0.35s_ease] object-cover"
                  />
                  <button
                    type="button"
                    onClick={() => removePhoto(photo)}
                    aria-label={`Remove ${slot.label} photo`}
                    className="absolute right-1.5 top-1.5 grid h-6 w-6 place-items-center rounded-full bg-black/60 text-xs text-white backdrop-blur transition hover:bg-black/80"
                  >
                    ×
                  </button>
                </>
              ) : state?.status === "uploading" ? (
                <span className="h-5 w-5 animate-spin rounded-full border-2 border-line-strong border-t-sage" />
              ) : state?.status === "error" ? (
                <span className="px-1 text-[9px] leading-tight text-[#a4553f]">
                  {state.error || "Failed"}
                </span>
              ) : (
                slot.label
              )}
            </div>
          );
        })}
      </div>

      <div className="mt-5 h-2 overflow-hidden rounded-full bg-paper-2">
        <div
          className="h-full rounded-full bg-sage transition-[width] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="mt-2 flex items-center justify-between text-[12px] text-faint">
        <span>
          {count} / {MAX_PHOTOS} photos
        </span>
        <span>{isReady ? "Ready ✓" : "Add a front or full-body photo"}</span>
      </div>
      {loadError && (
        <p className="mt-2 text-[12px] text-[#a4553f]" role="alert">
          {loadError}
        </p>
      )}
      {!loaded && !loadError && (
        <p className="mt-2 text-[12px] text-faint">Loading your fitting profile…</p>
      )}
    </div>
  );
}

function photoForSlot(index: number, photos: UserPhoto[]): UserPhoto | undefined {
  const slot = SLOTS[index];
  if (slot.kind !== "extra") return photos.find((p) => p.kind === slot.kind);
  // "extra" slots: fill in order with whichever extras exist beyond the
  // named slots, by upload order.
  const extraIndex = SLOTS.slice(0, index).filter((s) => s.kind === "extra").length;
  const extras = photos.filter((p) => p.kind === "extra");
  return extras[extraIndex];
}
