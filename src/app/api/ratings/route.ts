import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";

// Legt eine Bewertung an oder aktualisiert die bestehende (1 Bewertung pro User+Ziel).
// avg_rating/ratings_count werden hier direkt neu berechnet — PocketBase kennt
// keine Datenbank-Trigger wie Supabase/Postgres.
export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "Nicht angemeldet" }, { status: 401 });

  const { targetType, seriesId, movieId, episodeId, value } = await req.json();

  if (!targetType || !value || value < 1 || value > 10) {
    return NextResponse.json({ error: "Ungültige Bewertung" }, { status: 400 });
  }

  const pb = await createAdminClient();

  const targetField = targetType === "SERIES" ? "series_id" : targetType === "MOVIE" ? "movie_id" : "episode_id";
  const targetId = targetType === "SERIES" ? seriesId : targetType === "MOVIE" ? movieId : episodeId;

  let rating;
  try {
    const existing = await pb
      .collection(COL.ratings)
      .getFirstListItem(
        pb.filter("user_id = {:uid} && target_type = {:tt} && " + targetField + " = {:tid}", {
          uid: user.id,
          tt: targetType,
          tid: targetId,
        })
      )
      .catch(() => null);

    if (existing) {
      rating = await pb.collection(COL.ratings).update(existing.id, { value });
    } else {
      rating = await pb.collection(COL.ratings).create({
        user_id: user.id,
        target_type: targetType,
        series_id: seriesId ?? null,
        movie_id: movieId ?? null,
        episode_id: episodeId ?? null,
        value,
      });
    }
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }

  // Ø-Bewertung neu berechnen — nur für Serien/Filme relevant (Episoden zeigen keinen Schnitt).
  if (targetType === "SERIES" || targetType === "MOVIE") {
    const collection = targetType === "SERIES" ? COL.series : COL.movies;
    const all = await pb.collection(COL.ratings).getFullList({
      filter: pb.filter("target_type = {:tt} && " + targetField + " = {:tid}", { tt: targetType, tid: targetId }),
    });
    const values = all.map((d: any) => d.value as number);
    const avg = values.reduce((a, b) => a + b, 0) / values.length;
    await pb.collection(collection).update(targetId, {
      avg_rating: Math.round(avg * 10) / 10,
      ratings_count: values.length,
    });
  }

  return NextResponse.json(rating);
}
