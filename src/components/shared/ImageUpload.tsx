"use client";

import { useState } from "react";
import { UploadCloud } from "lucide-react";
import { createBrowserClient } from "@/lib/pocketbase/client";
import { COL } from "@/lib/pocketbase/collections";

interface Props {
  bucket: "thumbnails" | "avatars"; // nur noch als Label genutzt, alle Bilder landen in derselben "uploads"-Collection
  pathPrefix: string;
  value: string;
  onChange: (url: string) => void;
  label: string;
  aspect?: "square" | "portrait" | "wide";
}

const ASPECT_CLASS: Record<string, string> = {
  square: "aspect-square",
  portrait: "aspect-[2/3]",
  wide: "aspect-video",
};

export default function ImageUpload({ value, onChange, label, aspect = "square" }: Props) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);

    try {
      const pb = createBrowserClient();
      const formData = new FormData();
      formData.append("file", file);

      const record = await pb.collection(COL.uploads).create(formData);
      const url = pb.files.getUrl(record, record.file);
      onChange(url);
    } catch {
      setError("Upload fehlgeschlagen. Bitte erneut versuchen.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-neutral-400">{label}</label>
      <div className="flex items-center gap-3">
        <div className={`relative ${ASPECT_CLASS[aspect]} w-20 shrink-0 overflow-hidden rounded-lg bg-neutral-800`}>
          {value ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={value} alt="" className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full items-center justify-center text-neutral-600">
              <UploadCloud className="h-6 w-6" />
            </div>
          )}
        </div>

        <label className="flex-1 cursor-pointer rounded-lg border border-white/10 bg-neutral-800 px-3 py-2 text-center text-xs text-neutral-300 hover:bg-neutral-700">
          {uploading ? "Wird hochgeladen…" : "Aus Galerie wählen"}
          <input type="file" accept="image/*" onChange={handleFile} disabled={uploading} className="hidden" />
        </label>
      </div>
      {error && <p className="mt-1 text-xs text-red-400">{error}</p>}
    </div>
  );
}
