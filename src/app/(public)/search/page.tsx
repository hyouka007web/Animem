import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import SearchBar from "@/components/search/SearchBar";
import PosterCard from "@/components/shared/PosterCard";

export default async function SearchPage({ searchParams }: { searchParams: { q?: string } }) {
  const query = searchParams.q?.trim().toLowerCase() ?? "";
  const pb = await createAdminClient();

  // PocketBase-Filter können Teilstrings zwar per "~" matchen, aber case-
  // insensitiv und robust gegen Sonderzeichen ist reines JS-Filtern
  // zuverlässiger — der Katalog bleibt bei diesem Projekt überschaubar.
  const [allSeries, allMovies] = await Promise.all([
    pb.collection(COL.series).getFullList({ filter: 'status = "PUBLISHED"', sort: "title" }),
    pb.collection(COL.movies).getFullList({ filter: 'status = "PUBLISHED"', sort: "title" }),
  ]);

  const filterFn = (item: any) => !query || item.title.toLowerCase().includes(query);
  const series = allSeries.filter(filterFn).slice(0, 24);
  const movies = allMovies.filter(filterFn).slice(0, 24);

  const hasResults = series.length + movies.length > 0;

  return (
    <div className="realm-backdrop min-h-screen px-4 py-8 text-white">
      <div className="relative mx-auto max-w-5xl">
        <h1 className="mb-4 text-2xl font-bold">Suche</h1>
        <SearchBar />

        {!hasResults && <p className="text-sm text-neutral-500">Keine Ergebnisse gefunden.</p>}

        {!!series.length && (
          <>
            <h2 className="mb-3 text-lg font-semibold">Serien</h2>
            <div className="mb-8 grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-6">
              {series.map((s) => (
                <PosterCard key={s.id} href={`/series/${s.slug}`} title={s.title} thumb={s.thumbnail_url} />
              ))}
            </div>
          </>
        )}

        {!!movies.length && (
          <>
            <h2 className="mb-3 text-lg font-semibold">Filme</h2>
            <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-6">
              {movies.map((m) => (
                <PosterCard key={m.id} href={`/movies/${m.slug}`} title={m.title} thumb={m.thumbnail_url} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
