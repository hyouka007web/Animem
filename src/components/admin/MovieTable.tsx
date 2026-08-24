"use client";

import { useState } from "react";
import Image from "next/image";
import { Pencil, Trash2, Plus, X } from "lucide-react";
import ImageUpload from "@/components/shared/ImageUpload";

interface MovieRow {
  id: string;
  title: string;
  thumbnail_url: string;
  embed_url: string;
  status: string;
  avg_rating: number;
}

const emptyForm = { title: "", description: "", thumbnailUrl: "", embedUrl: "", status: "DRAFT" };

export default function MovieTable({ initialMovies }: { initialMovies: MovieRow[] }) {
  const [movies, setMovies] = useState(initialMovies);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<MovieRow | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function openNew() {
    setEditing(null);
    setForm(emptyForm);
    setError(null);
    setOpen(true);
  }

  function openEdit(m: MovieRow) {
    setEditing(m);
    setForm({
      title: m.title,
      description: "",
      thumbnailUrl: m.thumbnail_url,
      embedUrl: m.embed_url,
      status: m.status,
    });
    setError(null);
    setOpen(true);
  }

  async function handleDelete(id: string) {
    if (!confirm("Diesen Film wirklich löschen?")) return;
    setError(null);
    const res = await fetch(`/api/movies/${id}`, { method: "DELETE" });
    if (res.ok) {
      setMovies((prev) => prev.filter((m) => m.id !== id));
    } else {
      const body = await res.json().catch(() => null);
      setError(body?.error || "Löschen fehlgeschlagen.");
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    const isEdit = Boolean(editing);
    const res = await fetch(isEdit ? `/api/movies/${editing!.id}` : "/api/movies", {
      method: isEdit ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...form, genres: [] }),
    });
    setSaving(false);
    if (res.ok) {
      const saved = await res.json();
      setMovies((prev) => (isEdit ? prev.map((m) => (m.id === saved.id ? saved : m)) : [saved, ...prev]));
      setOpen(false);
    } else {
      const body = await res.json().catch(() => null);
      setError(body?.error || "Speichern fehlgeschlagen.");
    }
  }

  return (
    <div>
      {error && (
        <p className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-300">
          {error}
        </p>
      )}
      <button
        onClick={openNew}
        className="mb-4 flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
      >
        <Plus className="h-4 w-4" /> Neuer Film
      </button>

      <div className="overflow-hidden rounded-xl border border-white/10">
        <table className="w-full text-left text-sm">
          <thead className="bg-white/5 text-neutral-400">
            <tr>
              <th className="px-4 py-3 font-medium">Film</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">⌀ Bewertung</th>
              <th className="px-4 py-3 font-medium text-right">Aktionen</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {movies.map((m) => (
              <tr key={m.id} className="hover:bg-white/[0.03]">
                <td className="flex items-center gap-3 px-4 py-3">
                  <div className="relative h-10 w-10 overflow-hidden rounded-md bg-neutral-800">
                    <Image src={m.thumbnail_url} alt={m.title} fill className="object-cover" />
                  </div>
                  {m.title}
                </td>
                <td className="px-4 py-3 text-neutral-400">{m.status}</td>
                <td className="px-4 py-3 text-neutral-400">{Number(m.avg_rating).toFixed(1)}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    <button onClick={() => openEdit(m)} className="rounded-md p-2 text-neutral-400 hover:bg-white/10 hover:text-white">
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button onClick={() => handleDelete(m.id)} className="rounded-md p-2 text-neutral-400 hover:bg-red-500/10 hover:text-red-400">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-neutral-900 p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold">{editing ? "Film bearbeiten" : "Neuer Film"}</h2>
              <button onClick={() => setOpen(false)} className="text-neutral-400 hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-3">
              <input
                required
                placeholder="Titel"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                className="w-full rounded-lg border border-white/10 bg-neutral-800 px-3 py-2 text-sm outline-none focus:border-indigo-500"
              />
              <textarea
                placeholder="Beschreibung"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                rows={3}
                className="w-full rounded-lg border border-white/10 bg-neutral-800 px-3 py-2 text-sm outline-none focus:border-indigo-500"
              />
              <ImageUpload
                bucket="thumbnails"
                pathPrefix="movies"
                value={form.thumbnailUrl}
                onChange={(url) => setForm({ ...form, thumbnailUrl: url })}
                label="Thumbnail"
                aspect="portrait"
              />
              <input
                required
                placeholder="Embed-URL / Iframe-Link des Hosters"
                value={form.embedUrl}
                onChange={(e) => setForm({ ...form, embedUrl: e.target.value })}
                className="w-full rounded-lg border border-white/10 bg-neutral-800 px-3 py-2 text-sm outline-none focus:border-indigo-500"
              />
              <select
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value })}
                className="w-full rounded-lg border border-white/10 bg-neutral-800 px-3 py-2 text-sm outline-none focus:border-indigo-500"
              >
                <option value="DRAFT">Entwurf</option>
                <option value="PUBLISHED">Veröffentlicht</option>
                <option value="ARCHIVED">Archiviert</option>
              </select>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setOpen(false)} className="px-4 py-2 text-sm text-neutral-300">
                  Abbrechen
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
                >
                  {saving ? "Speichern…" : "Speichern"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
