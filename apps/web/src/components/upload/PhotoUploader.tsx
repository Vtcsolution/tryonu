"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { resolveMediaUrl } from "@/lib/api/client";
import { photos as photosApi } from "@/lib/api/endpoints";
import type { PhotoKind, UserPhoto } from "@/lib/api/types";

const SLOTS: { kind: PhotoKind; label: string; required: boolean }[] = [
  { kind: "front", label: "Front", required: true },
  { kind: "back", label: "Back", required: false },
  { kind: "left_side", label: "Left", required: false },
  { kind: "right_side", label: "Right", required: false },
];

const MAX_PHOTOS = SLOTS.length;
// Below this long side a try-on comes back soft or grainy: the engine has to
// invent detail, and every extra product redraws the whole image again.
const LOW_RES_LONG_SIDE = 1200;
const RECOMMENDED_HEIGHT = 1500;

function isLowRes(photo: UserPhoto): boolean {
  return photo.width != null && photo.height != null && Math.max(photo.width, photo.height) < LOW_RES_LONG_SIDE;
}
export const MIN_PHOTOS = SLOTS.filter((s) => s.required).length; // just the front

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
    const isReady = SLOTS.filter((s) => s.required).every((s) =>
      photos.some((p) => p.kind === s.kind)
    );
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
  const requiredSlots = SLOTS.filter((s) => s.required);
  const requiredCount = requiredSlots.filter((s) => photos.some((p) => p.kind === s.kind)).length;
  const pct = Math.min(100, Math.round((requiredCount / MIN_PHOTOS) * 100));
  const isReady = requiredCount === MIN_PHOTOS;

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
          JPG, PNG, WEBP or HEIC · up to 12MB each · front required · back and sides optional
        </p>
      </div>

      <div className="mt-4 rounded-2xl border border-line bg-paper-2/60 px-4 py-3 text-left text-[12.5px] leading-relaxed text-muted">
        <p className="font-semibold text-ink">For the sharpest result</p>
        <ul className="mt-1 list-disc space-y-0.5 pl-4">
          <li>One person, full body visible from head to feet, standing straight</li>
          <li>Sharp and well lit; no filters, no heavy blur</li>
          <li>
            At least {RECOMMENDED_HEIGHT}px tall (an original phone photo, not a screenshot or a forwarded
            WhatsApp copy)
          </li>
        </ul>
      </div>

      <div className="mt-5 grid grid-cols-4 gap-2.5">
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
                  {isLowRes(photo) && (
                    <span className="absolute inset-x-1.5 bottom-1.5 rounded-md bg-[#a4553f]/90 px-1 py-0.5 text-[9px] font-semibold text-white">
                      Low resolution
                    </span>
                  )}
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
        <span>{isReady ? "Ready ✓" : "Add a front photo"}</span>
      </div>
      {photos.filter(isLowRes).map((photo) => (
        <p key={photo.id} className="mt-2 text-[12px] text-[#a4553f]" role="alert">
          Your {SLOTS.find((s) => s.kind === photo.kind)?.label.toLowerCase() ?? ""} photo is only {photo.width}×
          {photo.height}px, so the try-on may look blurry or grainy. For a sharp result, replace it with one at
          least {RECOMMENDED_HEIGHT}px tall.
        </p>
      ))}
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
  return photos.find((p) => p.kind === SLOTS[index].kind);
}
