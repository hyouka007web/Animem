import { NextRequest } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { resolveTaxonomyIds, loadTaxonomyNames } from "@/lib/pocketbase/taxonomy";
import { getCurrentUser } from "@/lib/auth";
import { can } from "@/lib/permissions";
import { uniqueSlug } from "@/lib/slugify";
import { seriesSchema } from "@/lib/validation";
import { noStoreJson, rateLimit, rateLimitResponse, safeError } from "@/lib/security";
import type PocketBase from "pocketbase";

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
  const result = await pb.collection(COL.series).getList(page, perPage, { filter, sort: "-avg_rating" });
  return noStoreJson(result.items);
}

export async function loadFullSeries(pb: PocketBase, seriesId: string) {
  const series = await pb.collection(COL.series).getOne(seriesId).catch(() => null);
  if (!series) return null;
  const seasonsRaw = await pb.collection(COL.seasons).getFullList({ filter: pb.filter("series_id = {:id}", { id: seriesId }), sort: "number" });
  const seasons = await Promise.all(seasonsRaw.map(async (season) => ({
    ...season,
    episodes: await pb.collection(COL.episodes).getFullList({ filter: pb.filter("season_id = {:id}", { id: season.id }), sort: "number" }),
  })));
  const [genres, tags] = await Promise.all([
    loadTaxonomyNames(pb, COL.genres, (series.genre_ids as string[]) ?? [], "genre"),
    loadTaxonomyNames(pb, COL.tags, (series.tag_ids as string[]) ?? [], "tag"),
  ]);
  return { ...series, seasons, genres, tags };
}

async function deleteSeriesChildren(pb: PocketBase, seriesId: string) {
  const seasons = await pb.collection(COL.seasons).getFullList({ filter: pb.filter("series_id = {:id}", { id: seriesId }) });
  for (const season of seasons) {
    const episodes = await pb.collection(COL.episodes).getFullList({ filter: pb.filter("season_id = {:id}", { id: season.id }) });
    await Promise.all(episodes.map((ep) => pb.collection(COL.episodes).delete(ep.id)));
    await pb.collection(COL.seasons).delete(season.id);
  }
}

export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user || !can.manageContent(user.role)) return noStoreJson({ error: "Nicht berechtigt" }, { status: 403 });
  const limit = rateLimit(req, `series-create:${user.id}`, 20, 60_000);
  if (!limit.allowed) return rateLimitResponse(limit.retryAfter);
  const parsed = seriesSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return noStoreJson({ error: "Ungültige Seriendaten." }, { status: 400 });

  const pb = await createAdminClient();
  const genreIds = await resolveTaxonomyIds(pb, COL.genres, parsed.data.genres);
  const tagIds = await resolveTaxonomyIds(pb, COL.tags, parsed.data.tags);
  let series: any;
  try {
    series = await pb.collection(COL.series).create({
      title: parsed.data.title, slug: await uniqueSlug(pb, COL.series, parsed.data.title), description: parsed.data.description,
      thumbnail_url: parsed.data.thumbnailUrl, banner_url: parsed.data.bannerUrl, status: parsed.data.status,
      created_by: user.id, genre_ids: genreIds, tag_ids: tagIds, avg_rating: 0, ratings_count: 0, view_count: 0,
    });
    for (const season of parsed.data.seasons) {
      const createdSeason = await pb.collection(COL.seasons).create({ series_id: series.id, number: season.number, title: season.title });
      for (const ep of season.episodes) {
        await pb.collection(COL.episodes).create({ season_id: createdSeason.id, number: ep.number, title: ep.title, embed_url: ep.embedUrl, embed_provider: ep.embedProvider, status: "PUBLISHED" });
      }
    }
  } catch (error) {
    if (series?.id) {
      await deleteSeriesChildren(pb, series.id).catch(() => undefined);
      await pb.collection(COL.series).delete(series.id).catch(() => undefined);
    }
    return noStoreJson({ error: safeError(error, "Serie konnte nicht erstellt werden.") }, { status: 500 });
  }

  const full = await loadFullSeries(pb, series.id);
  return full ? noStoreJson(full, { status: 201 }) : noStoreJson({ error: "Serie konnte nach dem Speichern nicht geladen werden." }, { status: 500 });
}
