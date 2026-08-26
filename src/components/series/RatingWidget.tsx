"use client";

import { useState } from "react";
import { Star } from "lucide-react";

interface Props {
  targetType: "SERIES" | "MOVIE" | "EPISODE";
  seriesId?: string;
  movieId?: string;
  episodeId?: string;
  initialValue: number | null; // 1-10 Skala (Sterne * 2)
}

export default function RatingWidget({ targetType, seriesId, movieId, episodeId, initialValue }: Props) {
  const [value, setValue] = useState(initialValue ?? 0);
  const [hover, setHover] = useState(0);
  const [saving, setSaving] = useState(false);

  async function rate(stars: number) {
    setSaving(true);
    const res = await fetch("/api/ratings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        targetType,
        seriesId,
        movieId,
        episodeId,
        value: stars * 2, // 5 Sterne im UI -> 1-10 Skala in der DB
      }),
    });
    if (res.ok) setValue(stars * 2);
    setSaving(false);
  }

  const displayedStars = Math.round((hover || value) / 2);

  return (
    <div className="flex items-center gap-1" onMouseLeave={() => setHover(0)}>
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          disabled={saving}
          onMouseEnter={() => setHover(star * 2)}
          onClick={() => rate(star)}
          className="p-0.5"
        >
          <Star
            className={`h-5 w-5 ${
              star <= displayedStars ? "fill-amber-400 text-amber-400" : "text-neutral-600"
            }`}
          />
        </button>
      ))}
    </div>
  );
}
