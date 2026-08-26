import { NextRequest } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { enrichWithTargets } from "@/lib/pocketbase/enrich";
import { watchlistSchema } from "@/lib/validation";
import { noStoreJson, rateLimit, rateLimitResponse, safeError } from "@/lib/security";

export async function GET() {
  const user = await getCurrentUser();
  if (!user) return noStoreJson({ error: "Nicht angemeldet" }, { status: 401 });
  const pb = await createAdminClient();
  const raw = await pb.collection(COL.watchlistItems).getList(1, 200, {
    filter: pb.filter("user_id = {:uid}", { uid: user.id }), sort: "-created",
  });
  return noStoreJson(await enrichWithTargets(pb, raw.items));
}

export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return noStoreJson({ error: "Nicht angemeldet" }, { status: 401 });
  const limit = rateLimit(req, `watchlist:${user.id}`, 30, 60_000);
  if (!limit.allowed) return rateLimitResponse(limit.retryAfter);
  const parsed = watchlistSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return noStoreJson({ error: "Genau eine Serie oder ein Film muss angegeben werden." }, { status: 400 });

  const pb = await createAdminClient();
  const field = parsed.data.seriesId ? "series_id" : "movie_id";
  const value = parsed.data.seriesId ?? parsed.data.movieId;
  const collection = parsed.data.seriesId ? COL.series : COL.movies;
  try { await pb.collection(collection).getOne(value!); }
  catch { return noStoreJson({ error: "Ziel nicht gefunden." }, { status: 404 }); }

  const existing = await pb.collection(COL.watchlistItems).getFirstListItem(
    pb.filter(`user_id = {:uid} && ${field} = {:value}`, { uid: user.id, value }),
  ).catch(() => null);
  if (existing) return noStoreJson(existing);

  try {
    const data = await pb.collection(COL.watchlistItems).create({ user_id: user.id, series_id: parsed.data.seriesId ?? null, movie_id: parsed.data.movieId ?? null });
    return noStoreJson(data, { status: 201 });
  } catch (error) {
    const raced = await pb.collection(COL.watchlistItems).getFirstListItem(pb.filter(`user_id = {:uid} && ${field} = {:value}`, { uid: user.id, value })).catch(() => null);
    if (raced) return noStoreJson(raced);
    return noStoreJson({ error: safeError(error, "Watchlist konnte nicht aktualisiert werden.") }, { status: 500 });
  }
}

export async function DELETE(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return noStoreJson({ error: "Nicht angemeldet" }, { status: 401 });
  const parsed = watchlistSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return noStoreJson({ error: "Ungültiges Watchlist-Ziel." }, { status: 400 });
  const pb = await createAdminClient();
  const field = parsed.data.seriesId ? "series_id" : "movie_id";
  const value = parsed.data.seriesId ?? parsed.data.movieId;
  const existing = await pb.collection(COL.watchlistItems).getFullList({ filter: pb.filter(`user_id = {:uid} && ${field} = {:v}`, { uid: user.id, v: value }) });
  await Promise.all(existing.map((doc) => pb.collection(COL.watchlistItems).delete(doc.id)));
  return noStoreJson({ success: true });
}
