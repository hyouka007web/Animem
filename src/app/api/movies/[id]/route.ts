import { NextRequest } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { can } from "@/lib/permissions";
import { resolveTaxonomyIds } from "@/lib/pocketbase/taxonomy";
import { uniqueSlug } from "@/lib/slugify";
import { movieUpdateSchema } from "@/lib/validation";
import { noStoreJson, rateLimit, rateLimitResponse, safeError } from "@/lib/security";

export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
  const user = await getCurrentUser();
  if (!user || !can.manageContent(user.role)) return noStoreJson({ error: "Nicht berechtigt" }, { status: 403 });
  const limit = rateLimit(req, `movie-update:${user.id}`, 60, 60_000);
  if (!limit.allowed) return rateLimitResponse(limit.retryAfter);
  const parsed = movieUpdateSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return noStoreJson({ error: "Ungültige Filmdaten." }, { status: 400 });

  const pb = await createAdminClient();
  const existing = await pb.collection(COL.movies).getOne(params.id).catch(() => null);
  if (!existing) return noStoreJson({ error: "Film nicht gefunden" }, { status: 404 });

  const data: Record<string, unknown> = {};
  if (parsed.data.title !== undefined) { data.title = parsed.data.title; data.slug = await uniqueSlug(pb, COL.movies, parsed.data.title, params.id); }
  if (parsed.data.description !== undefined) data.description = parsed.data.description;
  if (parsed.data.thumbnailUrl !== undefined) data.thumbnail_url = parsed.data.thumbnailUrl;
  if (parsed.data.bannerUrl !== undefined) data.banner_url = parsed.data.bannerUrl;
  if (parsed.data.embedUrl !== undefined) data.embed_url = parsed.data.embedUrl;
  if (parsed.data.embedProvider !== undefined) data.embed_provider = parsed.data.embedProvider;
  if (parsed.data.status !== undefined) data.status = parsed.data.status;
  if (parsed.data.genres !== undefined) data.genre_ids = resolveTaxonomyIds(pb, COL.genres, parsed.data.genres!);
  if (parsed.data.tags !== undefined) data.tag_ids = resolveTaxonomyIds(pb, COL.tags, parsed.data.tags!);

  try {
    return noStoreJson(await pb.collection(COL.movies).update(params.id, data));
  } catch (error) {
    return noStoreJson({ error: safeError(error, "Film konnte nicht gespeichert werden.") }, { status: 500 });
  }
}

export async function DELETE(_req: NextRequest, { params }: { params: { id: string } }) {
  const user = await getCurrentUser();
  if (!user || !can.manageAdmins(user.role)) return noStoreJson({ error: "Nicht berechtigt" }, { status: 403 });
  const pb = await createAdminClient();
  const movie = await pb.collection(COL.movies).getOne(params.id).catch(() => null);
  if (!movie) return noStoreJson({ error: "Film nicht gefunden" }, { status: 404 });
  try {
    const related = [
      [COL.ratings, pb.filter("movie_id = {:id}", { id: params.id })],
      [COL.watchlistItems, pb.filter("movie_id = {:id}", { id: params.id })],
      [COL.profileFavorites, pb.filter("movie_id = {:id}", { id: params.id })],
    ] as const;
    await Promise.all(related.map(async ([collection, filter]) => {
      const records = await pb.collection(collection).getFullList({ filter });
      await Promise.all(records.map((record) => pb.collection(collection).delete(record.id)));
    }));
    await pb.collection(COL.movies).delete(params.id);
    return noStoreJson({ success: true });
  } catch (error) {
    return noStoreJson({ error: safeError(error, "Film konnte nicht gelöscht werden.") }, { status: 500 });
  }
}
