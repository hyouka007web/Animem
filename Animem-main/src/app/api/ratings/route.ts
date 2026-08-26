import { NextRequest } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { ratingSchema } from "@/lib/validation";
import { noStoreJson, rateLimit, rateLimitResponse, safeError } from "@/lib/security";

export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return noStoreJson({ error: "Nicht angemeldet" }, { status: 401 });
  const limit = rateLimit(req, `rating:${user.id}`, 30, 60_000);
  if (!limit.allowed) return rateLimitResponse(limit.retryAfter);

  const parsed = ratingSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return noStoreJson({ error: "Ungültige Bewertung." }, { status: 400 });

  const { targetType, value } = parsed.data;
  const targetField = targetType === "SERIES" ? "series_id" : targetType === "MOVIE" ? "movie_id" : "episode_id";
  const targetId = targetType === "SERIES" ? parsed.data.seriesId! : targetType === "MOVIE" ? parsed.data.movieId! : parsed.data.episodeId!;
  const targetCollection = targetType === "SERIES" ? COL.series : targetType === "MOVIE" ? COL.movies : COL.episodes;

  const pb = await createAdminClient();
  let target: any;
  try { target = await pb.collection(targetCollection).getOne(targetId); }
  catch { return noStoreJson({ error: "Bewertungsziel nicht gefunden." }, { status: 404 }); }
  if (target.status && target.status !== "PUBLISHED") return noStoreJson({ error: "Dieses Ziel ist noch nicht veröffentlicht." }, { status: 403 });

  try {
    const existing = await pb.collection(COL.ratings).getFirstListItem(
      pb.filter(`user_id = {:uid} && target_type = {:tt} && ${targetField} = {:tid}`, { uid: user.id, tt: targetType, tid: targetId }),
    ).catch(() => null);

    const payload = {
      user_id: user.id,
      target_type: targetType,
      series_id: parsed.data.seriesId ?? null,
      movie_id: parsed.data.movieId ?? null,
      episode_id: parsed.data.episodeId ?? null,
      value,
    };
    let rating;
    if (existing) {
      rating = await pb.collection(COL.ratings).update(existing.id, { value });
    } else {
      try {
        rating = await pb.collection(COL.ratings).create(payload);
      } catch (createError) {
        const raced = await pb.collection(COL.ratings).getFirstListItem(
          pb.filter(`user_id = {:uid} && target_type = {:tt} && ${targetField} = {:tid}`, { uid: user.id, tt: targetType, tid: targetId }),
        ).catch(() => null);
        if (!raced) throw createError;
        rating = await pb.collection(COL.ratings).update(raced.id, { value });
      }
    }

    if (targetType === "SERIES" || targetType === "MOVIE") {
      const all = await pb.collection(COL.ratings).getFullList({
        filter: pb.filter(`target_type = {:tt} && ${targetField} = {:tid}`, { tt: targetType, tid: targetId }),
      });
      const values = all.map((d: any) => Number(d.value)).filter(Number.isFinite);
      const avg = values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0;
      await pb.collection(targetCollection).update(targetId, {
        avg_rating: Math.round(avg * 10) / 10,
        ratings_count: values.length,
      });
    }

    return noStoreJson(rating);
  } catch (error) {
    return noStoreJson({ error: safeError(error, "Bewertung konnte nicht gespeichert werden.") }, { status: 500 });
  }
}
