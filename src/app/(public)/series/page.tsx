import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import PosterCard from "@/components/shared/PosterCard";

export default async function SeriesListPage() {
  const pb = await createAdminClient();
  const series = await pb.collection(COL.series).getFullList({ filter: 'status = "PUBLISHED"', sort: "title" });

  return (
    <div className="realm-backdrop min-h-screen px-4 py-8 text-white">
      <div className="relative mx-auto max-w-6xl">
        <h1 className="mb-6 text-2xl font-bold">Serien</h1>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
          {series.map((s) => (
            <PosterCard
              key={s.id}
              href={`/series/${s.slug}`}
              title={s.title}
              thumb={s.thumbnail_url}
              rating={Number(s.avg_rating)}
            />
          ))}
          {!series.length && (
            <p className="col-span-full text-sm text-neutral-500">Noch keine Serien veröffentlicht.</p>
          )}
        </div>
      </div>
    </div>
  );
}
