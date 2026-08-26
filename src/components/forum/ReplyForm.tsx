"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function ReplyForm({ threadId }: { threadId: string }) {
  const router = useRouter();
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    const res = await fetch("/api/forum/posts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ threadId, content }),
    });
    setSaving(false);
    if (res.ok) {
      setContent("");
      router.refresh();
    }
  }

  return (
    <form onSubmit={submit} className="mt-4 space-y-2">
      <textarea
        required
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="Antwort schreiben…"
        rows={3}
        className="w-full rounded-lg border border-white/10 bg-neutral-800 px-3 py-2 text-sm outline-none focus:border-indigo-500"
      />
      <button
        type="submit"
        disabled={saving}
        className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
      >
        {saving ? "Wird gesendet…" : "Antworten"}
      </button>
    </form>
  );
}
