import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { loadTaxonomyNames } from "@/lib/pocketbase/taxonomy";
import SeriesTable from "@/components/admin/SeriesTable";

export default async function AdminSeriesPage() {
  const pb = await createAdminClient();
  const seriesRaw = await pb.collection(COL.series).getFullList({ sort: "-created" });

  const seriesWithMeta = await Promise.all(
    seriesRaw.map(async (s) => {
      const seasonsRaw = await pb
        .collection(COL.seasons)
        .getFullList({ filter: pb.filter("series_id = {:id}", { id: s.id }) });
      const seasons = await Promise.all(
        seasonsRaw.map(async (season) => {
          const episodes = await pb
            .collection(COL.episodes)
            .getFullList({ filter: pb.filter("season_id = {:id}", { id: season.id }) });
          return { ...season, episodes };
        })
      );

      const [genres, tags] = await Promise.all([
        loadTaxonomyNames(pb, COL.genres, (s.genre_ids as string[]) ?? [], "genre"),
        loadTaxonomyNames(pb, COL.tags, (s.tag_ids as string[]) ?? [], "tag"),
      ]);

      return { ...s, seasons, genres, tags };
    })
  );

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Serien verwalten</h1>
      </div>
      <SeriesTable initialSeries={seriesWithMeta as any} />
    </div>
  );
}
