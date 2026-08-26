import { NextRequest } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { favoriteSchema } from "@/lib/validation";
import { noStoreJson, rateLimit, rateLimitResponse, safeError } from "@/lib/security";

export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return noStoreJson({ error: "Nicht angemeldet" }, { status: 401 });
  const limit = rateLimit(req, `favorites:${user.id}`, 20, 60_000);
  if (!limit.allowed) return rateLimitResponse(limit.retryAfter);
  const parsed = favoriteSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return noStoreJson({ error: "Genau ein gültiges Profil-Favorit-Ziel ist erforderlich." }, { status: 400 });

  const pb = await createAdminClient();
  const targetCollection = parsed.data.seriesId ? COL.series : COL.movies;
  const targetId = parsed.data.seriesId ?? parsed.data.movieId;
  try { await pb.collection(targetCollection).getOne(targetId!); }
  catch { return noStoreJson({ error: "Favorit nicht gefunden." }, { status: 404 }); }

  try {
    const existing = await pb.collection(COL.profileFavorites).getFirstListItem(pb.filter("user_id = {:uid} && rank = {:r}", { uid: user.id, r: parsed.data.rank })).catch(() => null);
    const payload = { series_id: parsed.data.seriesId ?? null, movie_id: parsed.data.movieId ?? null };
    const data = existing
      ? await pb.collection(COL.profileFavorites).update(existing.id, payload)
      : await pb.collection(COL.profileFavorites).create({ user_id: user.id, rank: parsed.data.rank, ...payload });
    return noStoreJson(data);
  } catch (error) {
    return noStoreJson({ error: safeError(error, "Favorit konnte nicht gespeichert werden.") }, { status: 500 });
  }
}

export async function DELETE(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return noStoreJson({ error: "Nicht angemeldet" }, { status: 401 });
  const rank = Number((await req.json().catch(() => null))?.rank);
  if (![1, 2, 3].includes(rank)) return noStoreJson({ error: "Ungültiger Platz" }, { status: 400 });
  const pb = await createAdminClient();
  const existing = await pb.collection(COL.profileFavorites).getFullList({ filter: pb.filter("user_id = {:uid} && rank = {:r}", { uid: user.id, r: rank }) });
  await Promise.all(existing.map((doc) => pb.collection(COL.profileFavorites).delete(doc.id)));
  return noStoreJson({ success: true });
}
