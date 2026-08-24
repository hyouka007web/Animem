import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import PosterCard from "@/components/shared/PosterCard";

export default async function MoviesListPage() {
  const pb = await createAdminClient();
  const movies = await pb.collection(COL.movies).getFullList({ filter: 'status = "PUBLISHED"', sort: "title" });

  return (
    <div className="realm-backdrop min-h-screen px-4 py-8 text-white">
      <div className="relative mx-auto max-w-6xl">
        <h1 className="mb-6 text-2xl font-bold">Filme</h1>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
          {movies.map((m) => (
            <PosterCard
              key={m.id}
              href={`/movies/${m.slug}`}
              title={m.title}
              thumb={m.thumbnail_url}
              rating={Number(m.avg_rating)}
            />
          ))}
          {!movies.length && (
            <p className="col-span-full text-sm text-neutral-500">Noch keine Filme veröffentlicht.</p>
          )}
        </div>
      </div>
    </div>
  );
}
