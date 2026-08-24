"use client";

import { useState } from "react";
import Image from "next/image";
import { Pencil, Trash2, Plus } from "lucide-react";
import SeriesFormModal, { type SeriesFormValues } from "./SeriesFormModal";

interface SeriesRow {
  id: string;
  title: string;
  thumbnail_url: string;
  status: string;
  avg_rating: number;
  seasons: { id: string; number: number; episodes: { id: string }[] }[];
}

export default function SeriesTable({ initialSeries }: { initialSeries: SeriesRow[] }) {
  const [series, setSeries] = useState(initialSeries);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<SeriesRow | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleDelete(id: string) {
    if (!confirm("Diese Serie inklusive aller Staffeln und Episoden wirklich löschen?")) return;
    setError(null);
    const res = await fetch(`/api/series/${id}`, { method: "DELETE" });
    if (res.ok) {
      setSeries((prev) => prev.filter((s) => s.id !== id));
    } else {
      const body = await res.json().catch(() => null);
      setError(body?.error || "Löschen fehlgeschlagen.");
    }
  }

  async function handleSave(values: SeriesFormValues) {
    setError(null);
    const isEdit = Boolean(editing);
    const res = await fetch(isEdit ? `/api/series/${editing!.id}` : "/api/series", {
      method: isEdit ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    });
    if (res.ok) {
      const saved = await res.json();
      setSeries((prev) =>
        isEdit ? prev.map((s) => (s.id === saved.id ? saved : s)) : [saved, ...prev]
      );
      setModalOpen(false);
      setEditing(null);
    } else {
      const body = await res.json().catch(() => null);
      setError(body?.error || "Speichern fehlgeschlagen.");
    }
  }

  const episodeCount = (row: SeriesRow) =>
    row.seasons.reduce((sum, s) => sum + s.episodes.length, 0);

  return (
    <div>
      {error && (
        <p className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-300">
          {error}
        </p>
      )}
      <button
        onClick={() => {
          setEditing(null);
          setModalOpen(true);
        }}
        className="mb-4 flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
      >
        <Plus className="h-4 w-4" />
        Neue Serie
      </button>

      <div className="overflow-hidden rounded-xl border border-white/10">
        <table className="w-full text-left text-sm">
          <thead className="bg-white/5 text-neutral-400">
            <tr>
              <th className="px-4 py-3 font-medium">Serie</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Staffeln</th>
              <th className="px-4 py-3 font-medium">Episoden</th>
              <th className="px-4 py-3 font-medium">⌀ Bewertung</th>
              <th className="px-4 py-3 font-medium text-right">Aktionen</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {series.map((row) => (
              <tr key={row.id} className="hover:bg-white/[0.03]">
                <td className="flex items-center gap-3 px-4 py-3">
                  <div className="relative h-10 w-10 overflow-hidden rounded-md bg-neutral-800">
                    <Image src={row.thumbnail_url} alt={row.title} fill className="object-cover" />
                  </div>
                  <span className="font-medium">{row.title}</span>
                </td>
                <td className="px-4 py-3 text-neutral-400">{row.status}</td>
                <td className="px-4 py-3 text-neutral-400">{row.seasons.length}</td>
                <td className="px-4 py-3 text-neutral-400">{episodeCount(row)}</td>
                <td className="px-4 py-3 text-neutral-400">{Number(row.avg_rating).toFixed(1)}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => {
                        setEditing(row);
                        setModalOpen(true);
                      }}
                      className="rounded-md p-2 text-neutral-400 hover:bg-white/10 hover:text-white"
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => handleDelete(row.id)}
                      className="rounded-md p-2 text-neutral-400 hover:bg-red-500/10 hover:text-red-400"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modalOpen && (
        <SeriesFormModal
          initialValues={
            editing
              ? {
                  title: editing.title,
                  description: (editing as any).description ?? "",
                  thumbnailUrl: editing.thumbnail_url,
                  bannerUrl: (editing as any).banner_url ?? "",
                  status: editing.status as SeriesFormValues["status"],
                  genres: ((editing as any).genres ?? []).map((g: any) => g.genre?.name).filter(Boolean),
                  tags: ((editing as any).tags ?? []).map((t: any) => t.tag?.name).filter(Boolean),
                  seasons: editing.seasons.map((s: any) => ({
                    id: s.id,
                    number: s.number,
                    title: s.title,
                    episodes: (s.episodes ?? []).map((e: any) => ({
                      id: e.id,
                      number: e.number,
                      title: e.title,
                      embedUrl: e.embed_url,
                      embedProvider: e.embed_provider,
                    })),
                  })),
                }
              : undefined
          }
          onClose={() => {
            setModalOpen(false);
            setEditing(null);
          }}
          onSave={handleSave}
        />
      )}
    </div>
  );
}
