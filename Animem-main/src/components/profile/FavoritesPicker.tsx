"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Crown, Pencil, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface Item {
  id: string;
  title: string;
}

interface FavoriteSlot {
  rank: number;
  series: { id: string; slug: string; title: string; thumbnail_url: string } | null;
  movie: { id: string; slug: string; title: string; thumbnail_url: string } | null;
}

const RANK_STYLE: Record<number, { height: string; ring: string; badge: string }> = {
  1: { height: "h-32", ring: "ring-2 ring-amber-400", badge: "bg-amber-400" },
  2: { height: "h-24", ring: "ring-2 ring-slate-300", badge: "bg-slate-300" },
  3: { height: "h-16", ring: "ring-2 ring-orange-400", badge: "bg-orange-400" },
};

export default function FavoritesPicker({
  favorites,
  allSeries,
  allMovies,
}: {
  favorites: FavoriteSlot[];
  allSeries: Item[];
  allMovies: Item[];
}) {
  const router = useRouter();
  const [editingRank, setEditingRank] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const bySlot = (rank: number) => favorites.find((f) => f.rank === rank);

  async function setFavorite(rank: number, value: string) {
    setSaving(true);
    setError(null);
    const [type, id] = value.split(":");
    const res = await fetch("/api/profile/favorites", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rank,
        seriesId: type === "series" ? id : null,
        movieId: type === "movie" ? id : null,
      }),
    });
    setSaving(false);
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      setError(body?.error || "Speichern fehlgeschlagen.");
      return;
    }
    setEditingRank(null);
    router.refresh();
  }

  async function clearFavorite(rank: number) {
    setSaving(true);
    await fetch("/api/profile/favorites", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rank }),
    });
    setSaving(false);
    router.refresh();
  }

  return (
    <div className="mb-8">
      <h2 className="mb-4 text-lg font-semibold">Mein Sieger-Treppchen</h2>
      <div className="flex items-end justify-center gap-4">
        {[2, 1, 3].map((rank) => {
          const slot = bySlot(rank);
          const item = slot?.series ?? slot?.movie;
          const style = RANK_STYLE[rank];

          return (
            <div key={rank} className="flex flex-col items-center">
              {item ? (
                <div className="relative">
                  {rank === 1 && (
                    <Crown className="absolute -top-6 left-1/2 h-6 w-6 -translate-x-1/2 text-amber-400" fill="currentColor" />
                  )}
                  <div className={cn("relative h-24 w-16 overflow-hidden rounded-lg bg-neutral-800", style.ring)}>
                    <Image src={item.thumbnail_url} alt={item.title} fill className="object-cover" />
                  </div>
                  <button
                    onClick={() => setEditingRank(rank)}
                    className="mt-1 flex w-full items-center justify-center gap-1 text-xs text-neutral-400 hover:text-white"
                  >
                    <Pencil className="h-3 w-3" /> Ändern
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setEditingRank(rank)}
                  className="flex h-24 w-16 items-center justify-center rounded-lg border border-dashed border-white/20 text-xs text-neutral-500 hover:border-indigo-500 hover:text-indigo-400"
                >
                  Auswählen
                </button>
              )}

              <div className={cn("mt-2 w-20 rounded-t-md", style.height, "bg-gradient-to-b from-white/10 to-transparent")} />
              <span className={cn("mt-1 flex h-5 w-5 items-center justify-center rounded-full text-xs font-bold text-black", style.badge)}>
                {rank}
              </span>

              {editingRank === rank && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
                  <div className="w-full max-w-sm rounded-2xl border border-white/10 bg-neutral-900 p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <p className="text-sm font-medium">Platz {rank} auswählen</p>
                      <button onClick={() => setEditingRank(null)} className="text-neutral-400 hover:text-white">
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                    <select
                      disabled={saving}
                      defaultValue=""
                      onChange={(e) => e.target.value && setFavorite(rank, e.target.value)}
                      className="w-full rounded-lg border border-white/10 bg-neutral-800 px-3 py-2 text-sm"
                    >
                      <option value="" disabled>
                        — auswählen —
                      </option>
                      <optgroup label="Serien">
                        {allSeries.map((s) => (
                          <option key={s.id} value={`series:${s.id}`}>
                            {s.title}
                          </option>
                        ))}
                      </optgroup>
                      <optgroup label="Filme">
                        {allMovies.map((m) => (
                          <option key={m.id} value={`movie:${m.id}`}>
                            {m.title}
                          </option>
                        ))}
                      </optgroup>
                    </select>
                    {item && (
                      <button
                        onClick={() => {
                          clearFavorite(rank);
                          setEditingRank(null);
                        }}
                        className="mt-3 text-xs text-red-400 hover:text-red-300"
                      >
                        Auswahl entfernen
                      </button>
                    )}
                    {error && <p className="mt-3 text-xs text-red-400">{error}</p>}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
