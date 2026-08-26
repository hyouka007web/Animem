import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import TopThreePodium from "@/components/podium/TopThreePodium";
import PosterCard from "@/components/shared/PosterCard";

export default async function HomePage() {
  const pb = await createAdminClient();

  const [top, latest] = await Promise.all([
    pb.collection(COL.series).getList(1, 3, { filter: 'status = "PUBLISHED"', sort: "-avg_rating" }),
    pb.collection(COL.series).getList(1, 12, { filter: 'status = "PUBLISHED"', sort: "-created" }),
  ]);

  const podiumData = top.items.map((s) => ({
    id: s.id,
    slug: s.slug,
    title: s.title,
    thumbnailUrl: s.thumbnail_url,
    avgRating: Number(s.avg_rating),
  }));

  return (
    <div className="realm-backdrop min-h-screen text-white">
      {podiumData.length === 3 && (
        <div className="relative">
          <TopThreePodium first={podiumData[0]} second={podiumData[1]} third={podiumData[2]} />
        </div>
      )}

      <section className="relative mx-auto max-w-6xl px-4 py-8">
        <h2 className="mb-4 text-xl font-bold">Neu hinzugefügt</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
          {latest.items.map((s) => (
            <PosterCard key={s.id} href={`/series/${s.slug}`} title={s.title} thumb={s.thumbnail_url} />
          ))}
        </div>
      </section>
    </div>
  );
}
