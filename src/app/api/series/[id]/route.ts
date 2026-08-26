import { NextRequest } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { resolveTaxonomyIds, loadTaxonomyNames } from "@/lib/pocketbase/taxonomy";
import { getCurrentUser } from "@/lib/auth";
import { can } from "@/lib/permissions";
import { seriesSchema } from "@/lib/validation";
import { noStoreJson, rateLimit, rateLimitResponse, safeError } from "@/lib/security";
import { uniqueSlug } from "@/lib/slugify";
import type PocketBase from "pocketbase";

async function loadFullSeries(pb: PocketBase, seriesId: string) {
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

async function deleteByFilter(pb: PocketBase, collection: string, filter: string) {
  const records = await pb.collection(collection).getFullList({ filter });
  await Promise.all(records.map((record) => pb.collection(collection).delete(record.id)));
}

export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
  const user = await getCurrentUser();
  if (!user || !can.manageContent(user.role)) return noStoreJson({ error: "Nicht berechtigt" }, { status: 403 });
  const limit = rateLimit(req, `series-update:${user.id}`, 30, 60_000);
  if (!limit.allowed) return rateLimitResponse(limit.retryAfter);
  const parsed = seriesSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return noStoreJson({ error: "Ungültige Seriendaten." }, { status: 400 });

  const pb = await createAdminClient();
  const existingSeries = await pb.collection(COL.series).getOne(params.id).catch(() => null);
  if (!existingSeries) return noStoreJson({ error: "Serie nicht gefunden" }, { status: 404 });

  try {
    const genreIds = await resolveTaxonomyIds(pb, COL.genres, parsed.data.genres);
    const tagIds = await resolveTaxonomyIds(pb, COL.tags, parsed.data.tags);
    await pb.collection(COL.series).update(params.id, {
      title: parsed.data.title, slug: await uniqueSlug(pb, COL.series, parsed.data.title, params.id), description: parsed.data.description,
      thumbnail_url: parsed.data.thumbnailUrl, banner_url: parsed.data.bannerUrl, status: parsed.data.status,
      genre_ids: genreIds, tag_ids: tagIds,
    });

    const existingSeasons = await pb.collection(COL.seasons).getFullList({ filter: pb.filter("series_id = {:id}", { id: params.id }) });
    const existingSeasonMap = new Map(existingSeasons.map((s) => [s.id, s]));
    const incomingSeasonIds = new Set<string>();

    for (const season of parsed.data.seasons) {
      let seasonId = season.id;
      if (seasonId) {
        const existingSeason = existingSeasonMap.get(seasonId);
        if (!existingSeason) return noStoreJson({ error: "Eine Staffel gehört nicht zu dieser Serie." }, { status: 400 });
        await pb.collection(COL.seasons).update(seasonId, { number: season.number, title: season.title });
      } else {
        const created = await pb.collection(COL.seasons).create({ series_id: params.id, number: season.number, title: season.title });
        seasonId = created.id;
      }
      incomingSeasonIds.add(seasonId);

      const existingEpisodes = await pb.collection(COL.episodes).getFullList({ filter: pb.filter("season_id = {:id}", { id: seasonId }) });
      const existingEpisodeMap = new Map(existingEpisodes.map((ep) => [ep.id, ep]));
      const incomingEpisodeIds = new Set<string>();
      for (const ep of season.episodes) {
        if (ep.id) {
          if (!existingEpisodeMap.has(ep.id)) return noStoreJson({ error: "Eine Episode gehört nicht zu dieser Staffel." }, { status: 400 });
          await pb.collection(COL.episodes).update(ep.id, { number: ep.number, title: ep.title, embed_url: ep.embedUrl, embed_provider: ep.embedProvider, status: "PUBLISHED" });
          incomingEpisodeIds.add(ep.id);
        } else {
          const created = await pb.collection(COL.episodes).create({ season_id: seasonId, number: ep.number, title: ep.title, embed_url: ep.embedUrl, embed_provider: ep.embedProvider, status: "PUBLISHED" });
          incomingEpisodeIds.add(created.id);
        }
      }
      await Promise.all(existingEpisodes.filter((ep) => !incomingEpisodeIds.has(ep.id)).map((ep) => pb.collection(COL.episodes).delete(ep.id)));
    }

    for (const season of existingSeasons.filter((s) => !incomingSeasonIds.has(s.id))) {
      const episodes = await pb.collection(COL.episodes).getFullList({ filter: pb.filter("season_id = {:id}", { id: season.id }) });
      await Promise.all(episodes.map((ep) => pb.collection(COL.episodes).delete(ep.id)));
      await pb.collection(COL.seasons).delete(season.id);
    }

    const full = await loadFullSeries(pb, params.id);
    return full ? noStoreJson(full) : noStoreJson({ error: "Serie nach dem Speichern nicht gefunden." }, { status: 500 });
  } catch (error) {
    return noStoreJson({ error: safeError(error, "Serie konnte nicht gespeichert werden.") }, { status: 500 });
  }
}

export async function DELETE(_req: NextRequest, { params }: { params: { id: string } }) {
  const user = await getCurrentUser();
  if (!user || !can.manageAdmins(user.role)) return noStoreJson({ error: "Nicht berechtigt" }, { status: 403 });
  const pb = await createAdminClient();
  const series = await pb.collection(COL.series).getOne(params.id).catch(() => null);
  if (!series) return noStoreJson({ error: "Serie nicht gefunden" }, { status: 404 });

  try {
    await deleteSeriesChildren(pb, params.id);
    const filters = [
      [COL.ratings, pb.filter("series_id = {:id}", { id: params.id })],
      [COL.watchlistItems, pb.filter("series_id = {:id}", { id: params.id })],
      [COL.subscriptions, pb.filter("series_id = {:id}", { id: params.id })],
      [COL.profileFavorites, pb.filter("series_id = {:id}", { id: params.id })],
    ] as const;
    await Promise.all(filters.map(([collection, filter]) => deleteByFilter(pb, collection, filter)));
    await pb.collection(COL.series).delete(params.id);
    return noStoreJson({ success: true });
  } catch (error) {
    return noStoreJson({ error: safeError(error, "Serie konnte nicht gelöscht werden.") }, { status: 500 });
  }
}
