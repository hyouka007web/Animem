"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import UserMention from "@/components/shared/UserMention";
import MentionText from "@/components/shared/MentionText";

interface Message {
  id: string;
  content: string;
  is_staff: boolean;
  created_at: string;
  sender: { username: string } | null;
}

export default function TicketChat({ ticketId, messages }: { ticketId: string; messages: Message[] }) {
  const router = useRouter();
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    const res = await fetch(`/api/tickets/${ticketId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    setSaving(false);
    if (res.ok) {
      setContent("");
      router.refresh();
    }
  }

  return (
    <div>
      <div className="space-y-3">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`rounded-lg p-3 text-sm ${
              m.is_staff ? "bg-indigo-600/20 border border-indigo-500/30" : "bg-neutral-800"
            }`}
          >
            <p className="mb-1 text-xs font-medium text-neutral-400">
              <UserMention username={m.sender?.username ?? ""} /> {m.is_staff && "· Support"}
            </p>
            <p className="whitespace-pre-wrap text-neutral-100">
              <MentionText text={m.content} />
            </p>
          </div>
        ))}
      </div>

      <form onSubmit={submit} className="mt-4 space-y-2">
        <textarea
          required
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Nachricht schreiben…"
          rows={3}
          className="w-full rounded-lg border border-white/10 bg-neutral-800 px-3 py-2 text-sm outline-none focus:border-indigo-500"
        />
        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {saving ? "Wird gesendet…" : "Senden"}
        </button>
      </form>
    </div>
  );
}
