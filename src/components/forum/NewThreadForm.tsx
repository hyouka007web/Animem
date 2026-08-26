"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function NewThreadForm({
  categoryId,
  categorySlug,
}: {
  categoryId: string;
  categorySlug: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    const res = await fetch("/api/forum/threads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ categoryId, title, content }),
    });
    setSaving(false);
    if (res.ok) {
      const thread = await res.json();
      router.push(`/forum/${categorySlug}/${thread.id}`);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
      >
        Neuen Thread erstellen
      </button>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-xl border border-white/10 bg-neutral-900/60 p-4">
      <input
        required
        placeholder="Titel"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        className="w-full rounded-lg border border-white/10 bg-neutral-800 px-3 py-2 text-sm outline-none focus:border-indigo-500"
      />
      <textarea
        required
        placeholder="Was möchtest du besprechen?"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={4}
        className="w-full rounded-lg border border-white/10 bg-neutral-800 px-3 py-2 text-sm outline-none focus:border-indigo-500"
      />
      <div className="flex justify-end gap-2">
        <button type="button" onClick={() => setOpen(false)} className="px-4 py-2 text-sm text-neutral-400">
          Abbrechen
        </button>
        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {saving ? "Wird erstellt…" : "Erstellen"}
        </button>
      </div>
    </form>
  );
}
