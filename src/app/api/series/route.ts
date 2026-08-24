import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { resolveTaxonomyIds, loadTaxonomyNames } from "@/lib/pocketbase/taxonomy";
import { getCurrentUser } from "@/lib/auth";
import { can } from "@/lib/permissions";
import { slugify } from "@/lib/slugify";
import type PocketBase from "pocketbase";

export async function GET(req: NextRequest) {
  const pb = await createAdminClient();
  const wantsAdmin = new URL(req.url).searchParams.get("admin") === "1";
  if (wantsAdmin) {
    const user = await getCurrentUser();
    if (!user || !can.manageContent(user.role)) return NextResponse.json({ error: "Nicht berechtigt" }, { status: 403 });
  }
  const filter = wantsAdmin ? "" : pb.filter("status = {:status}", { status: "PUBLISHED" });
  const series = await pb.collection(COL.series).getFullList({ filter, sort: "-avg_rating" });
  return NextResponse.json(series);
}

// Lädt eine Serie inkl. Staffeln/Episoden über getrennte, robuste Abfragen
// (PocketBase kennt keine verschachtelten Joins wie PostgREST).
async function loadFullSeries(pb: PocketBase, seriesId: string) {
  let series;
  try {
    series = await pb.collection(COL.series).getOne(seriesId);
  } catch {
    return null;
  }

  const seasonsRaw = await pb
    .collection(COL.seasons)
    .getFullList({ filter: pb.filter("series_id = {:id}", { id: seriesId }) });

  const seasons = await Promise.all(
    seasonsRaw.map(async (season) => {
      const episodes = await pb
        .collection(COL.episodes)
        .getFullList({ filter: pb.filter("season_id = {:id}", { id: season.id }) });
      return { ...season, episodes };
    })
  );

  const [genres, tags] = await Promise.all([
    loadTaxonomyNames(pb, COL.genres, (series.genre_ids as string[]) ?? [], "genre"),
    loadTaxonomyNames(pb, COL.tags, (series.tag_ids as string[]) ?? [], "tag"),
  ]);

  return { ...series, seasons, genres, tags };
}

export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user || !can.manageContent(user.role)) {
    return NextResponse.json({ error: "Nicht berechtigt" }, { status: 403 });
  }

  const body = await req.json();
  const { title, description, thumbnailUrl, bannerUrl, status, genres, tags, seasons } = body;

  if (!title || !thumbnailUrl) {
    return NextResponse.json({ error: "Titel und Thumbnail sind Pflichtfelder" }, { status: 400 });
  }

  const pb = await createAdminClient();

  const genreIds = await resolveTaxonomyIds(pb, COL.genres, (genres as string[]) ?? []);
  const tagIds = await resolveTaxonomyIds(pb, COL.tags, (tags as string[]) ?? []);

  let series;
  try {
    series = await pb.collection(COL.series).create({
      title,
      slug: slugify(title),
      description: description || "",
      thumbnail_url: thumbnailUrl,
      banner_url: bannerUrl || "",
      status: status || "DRAFT",
      created_by: user.id,
      genre_ids: genreIds,
      tag_ids: tagIds,
      avg_rating: 0,
      ratings_count: 0,
      view_count: 0,
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }

  for (const season of seasons ?? []) {
    const createdSeason = await pb.collection(COL.seasons).create({
      series_id: series.id,
      number: season.number,
      title: season.title || "",
    });

    for (const ep of season.episodes ?? []) {
      await pb.collection(COL.episodes).create({
        season_id: createdSeason.id,
        number: ep.number,
        title: ep.title,
        embed_url: ep.embedUrl,
        embed_provider: ep.embedProvider || "",
        status: "PUBLISHED",
      });
    }
  }

  const full = await loadFullSeries(pb, series.id);
  return NextResponse.json(full, { status: 201 });
}
