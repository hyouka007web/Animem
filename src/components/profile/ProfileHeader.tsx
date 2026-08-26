"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { UserCircle, Pencil, ExternalLink } from "lucide-react";
import ImageUpload from "@/components/shared/ImageUpload";

const ROLE_LABELS: Record<string, string> = {
  OWNER: "Owner",
  HEAD_ADMIN: "Head Admin",
  ADMIN: "Admin",
  USER: "User",
};

export default function ProfileHeader({
  userId,
  username,
  displayName,
  role,
  avatarUrl,
  bio,
}: {
  userId: string;
  username: string;
  displayName: string | null;
  role: string;
  avatarUrl: string | null;
  bio: string | null;
}) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [avatarInput, setAvatarInput] = useState(avatarUrl ?? "");
  const [bioInput, setBioInput] = useState(bio ?? "");
  const [displayNameInput, setDisplayNameInput] = useState(displayName ?? "");
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    const res = await fetch("/api/profile", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ avatarUrl: avatarInput, bio: bioInput, displayName: displayNameInput }),
    });
    setSaving(false);
    if (res.ok) {
      setEditing(false);
      router.refresh();
    }
  }

  return (
    <div className="mb-8 rounded-2xl border border-white/10 bg-neutral-900/60 p-6">
      <div className="flex items-start gap-4">
        {avatarUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={avatarUrl} alt={username} className="h-20 w-20 rounded-full object-cover" />
        ) : (
          <UserCircle className="h-20 w-20 text-neutral-500" />
        )}

        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold">{displayName || username}</h1>
            <span className="rounded-full bg-indigo-600/20 px-2 py-0.5 text-xs font-medium text-indigo-300">
              {ROLE_LABELS[role] ?? role}
            </span>
          </div>
          <p className="text-sm text-neutral-500">@{username}</p>

          {!editing && (
            <>
              <p className="mt-1 text-sm text-neutral-400">{bio || "Noch keine Beschreibung."}</p>
              <div className="mt-2 flex items-center gap-4">
                <button
                  onClick={() => setEditing(true)}
                  className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300"
                >
                  <Pencil className="h-3 w-3" /> Profil bearbeiten
                </button>
                <Link
                  href={`/u/${username}`}
                  className="flex items-center gap-1 text-xs text-neutral-500 hover:text-neutral-300"
                >
                  <ExternalLink className="h-3 w-3" /> So sehen dich andere
                </Link>
              </div>
            </>
          )}
        </div>
      </div>

      {editing && (
        <div className="mt-4 space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-neutral-400">Anzeigename</label>
            <input
              value={displayNameInput}
              onChange={(e) => setDisplayNameInput(e.target.value)}
              placeholder={username}
              className="w-full rounded-lg border border-white/10 bg-neutral-800 px-3 py-2 text-sm outline-none focus:border-indigo-500"
            />
            <p className="mt-1 text-xs text-neutral-500">
              Dein @{username} bleibt dabei immer gleich, das ist dein fester Handle.
            </p>
          </div>
          <div>
            <ImageUpload
              bucket="avatars"
              pathPrefix={userId}
              value={avatarInput}
              onChange={setAvatarInput}
              label="Profilbild"
              aspect="square"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-neutral-400">Beschreibung</label>
            <textarea
              value={bioInput}
              onChange={(e) => setBioInput(e.target.value)}
              rows={3}
              className="w-full rounded-lg border border-white/10 bg-neutral-800 px-3 py-2 text-sm outline-none focus:border-indigo-500"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setEditing(false)}
              className="rounded-lg px-4 py-2 text-sm text-neutral-300 hover:bg-white/5"
            >
              Abbrechen
            </button>
            <button
              onClick={save}
              disabled={saving}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              {saving ? "Speichern…" : "Speichern"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
