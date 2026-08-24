import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { resolveTaxonomyIds, loadTaxonomyNames } from "@/lib/pocketbase/taxonomy";
import { getCurrentUser } from "@/lib/auth";
import { can } from "@/lib/permissions";
import type PocketBase from "pocketbase";

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

export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
  const user = await getCurrentUser();
  if (!user || !can.manageContent(user.role)) {
    return NextResponse.json({ error: "Nicht berechtigt" }, { status: 403 });
  }

  const body = await req.json();
  const { title, description, thumbnailUrl, bannerUrl, status, genres, tags, seasons } = body;
  const pb = await createAdminClient();

  const updateData: Record<string, unknown> = {
    title,
    description: description || "",
    thumbnail_url: thumbnailUrl,
    banner_url: bannerUrl || "",
    status,
  };

  if (Array.isArray(genres)) updateData.genre_ids = await resolveTaxonomyIds(pb, COL.genres, genres);
  if (Array.isArray(tags)) updateData.tag_ids = await resolveTaxonomyIds(pb, COL.tags, tags);

  try {
    await pb.collection(COL.series).update(params.id, updateData);
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }

  if (Array.isArray(seasons)) {
    for (const season of seasons) {
      let seasonId = season.id as string | undefined;

      if (seasonId) {
        await pb.collection(COL.seasons).update(seasonId, {
          number: season.number,
          title: season.title || "",
        });
      } else {
        const createdSeason = await pb.collection(COL.seasons).create({
          series_id: params.id,
          number: season.number,
          title: season.title || "",
        });
        seasonId = createdSeason.id;
      }

      if (!seasonId) continue;

      for (const ep of season.episodes ?? []) {
        if (ep.id) {
          await pb.collection(COL.episodes).update(ep.id, {
            number: ep.number,
            title: ep.title,
            embed_url: ep.embedUrl,
            embed_provider: ep.embedProvider || "",
          });
        } else {
          await pb.collection(COL.episodes).create({
            season_id: seasonId,
            number: ep.number,
            title: ep.title,
            embed_url: ep.embedUrl,
            embed_provider: ep.embedProvider || "",
            status: "PUBLISHED",
          });
        }
      }
    }
  }

  const full = await loadFullSeries(pb, params.id);
  if (!full) return NextResponse.json({ error: "Serie nach dem Speichern nicht gefunden" }, { status: 500 });
  return NextResponse.json(full);
}

export async function DELETE(_req: NextRequest, { params }: { params: { id: string } }) {
  const user = await getCurrentUser();
  if (!user || !can.manageAdmins(user.role)) {
    return NextResponse.json({ error: "Nicht berechtigt" }, { status: 403 });
  }

  const pb = await createAdminClient();

  // Staffeln/Episoden mitlöschen, da PocketBase keine Fremdschlüssel-Kaskaden kennt.
  const seasons = await pb
    .collection(COL.seasons)
    .getFullList({ filter: pb.filter("series_id = {:id}", { id: params.id }) });

  for (const season of seasons) {
    const episodes = await pb
      .collection(COL.episodes)
      .getFullList({ filter: pb.filter("season_id = {:id}", { id: season.id }) });
    for (const ep of episodes) {
      await pb.collection(COL.episodes).delete(ep.id);
    }
    await pb.collection(COL.seasons).delete(season.id);
  }

  try {
    await pb.collection(COL.series).delete(params.id);
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
  return NextResponse.json({ success: true });
}
