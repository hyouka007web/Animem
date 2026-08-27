import { NextRequest } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { resolveTaxonomyIds } from "@/lib/pocketbase/taxonomy";
import { getCurrentUser } from "@/lib/auth";
import { can } from "@/lib/permissions";
import { uniqueSlug } from "@/lib/slugify";
import { movieSchema } from "@/lib/validation";
import { noStoreJson, rateLimit, rateLimitResponse, safeError } from "@/lib/security";

export async function GET(req: NextRequest) {
  const pb = await createAdminClient();
  const wantsAdmin = req.nextUrl.searchParams.get("admin") === "1";
  if (wantsAdmin) {
    const user = await getCurrentUser();
    if (!user || !can.manageContent(user.role)) return noStoreJson({ error: "Nicht berechtigt" }, { status: 403 });
  }
  const page = Math.max(1, Number(req.nextUrl.searchParams.get("page") || 1));
  const perPage = Math.min(50, Math.max(1, Number(req.nextUrl.searchParams.get("limit") || 24)));
  const filter = wantsAdmin ? "" : pb.filter("status = {:status}", { status: "PUBLISHED" });
  const result = await pb.collection(COL.movies).getList(page, perPage, { filter, sort: "-created" });
  return noStoreJson(result.items);
}

export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user || !can.manageContent(user.role)) return noStoreJson({ error: "Nicht berechtigt" }, { status: 403 });
  const limit = rateLimit(req, `movie-create:${user.id}`, 30, 60_000);
  if (!limit.allowed) return rateLimitResponse(limit.retryAfter);
  const parsed = movieSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return noStoreJson({ error: "Ungültige Filmdaten." }, { status: 400 });

  const pb = await createAdminClient();
  const genreIds = await resolveTaxonomyIds(pb, COL.genres, parsed.data.genres);
  const tagIds = await resolveTaxonomyIds(pb, COL.tags, parsed.data.tags);
  try {
    const movie = await pb.collection(COL.movies).create({
      title: parsed.data.title,
      slug: await uniqueSlug(pb, COL.movies, parsed.data.title),
      description: parsed.data.description,
      thumbnail_url: parsed.data.thumbnailUrl,
      banner_url: parsed.data.bannerUrl,
      embed_url: parsed.data.embedUrl,
      embed_provider: parsed.data.embedProvider,
      status: parsed.data.status,
      created_by: user.id,
      genre_ids: genreIds,
      tag_ids: tagIds,
      avg_rating: 0,
      ratings_count: 0,
    });
    return noStoreJson(movie, { status: 201 });
  } catch (error) {
    return noStoreJson({ error: safeError(error, "Film konnte nicht erstellt werden.") }, { status: 500 });
  }
}
