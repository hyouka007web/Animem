import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { findByTaxonomy } from "@/lib/pocketbase/taxonomy";

export default async function GenreDetailPage({ params }: { params: { slug: string } }) {
  const pb = await createAdminClient();

  const genre = await pb
    .collection(COL.genres)
    .getFirstListItem(pb.filter("slug = {:slug}", { slug: params.slug }))
    .catch(() => null);
  if (!genre) notFound();

  const [series, movies] = await Promise.all([
    findByTaxonomy(pb, COL.series, "genre_ids", genre!.id),
    findByTaxonomy(pb, COL.movies, "genre_ids", genre!.id),
  ]);

  return (
    <div className="min-h-screen bg-neutral-950 px-4 py-8 text-white">
      <div className="mx-auto max-w-6xl">
        <h1 className="mb-6 text-2xl font-bold">Kategorie: {genre!.name}</h1>

        {!!series.length && (
          <>
            <h2 className="mb-3 text-lg font-semibold">Serien</h2>
            <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
              {series.map((s: any) => (
                <Link key={s.id} href={`/series/${s.slug}`}>
                  <div className="relative aspect-[2/3] overflow-hidden rounded-lg bg-neutral-800">
                    <Image src={s.thumbnail_url} alt={s.title} fill className="object-cover" />
                  </div>
                  <p className="mt-2 truncate text-sm text-neutral-200">{s.title}</p>
                </Link>
              ))}
            </div>
          </>
        )}

        {!!movies.length && (
          <>
            <h2 className="mb-3 text-lg font-semibold">Filme</h2>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
              {movies.map((m: any) => (
                <Link key={m.id} href={`/movies/${m.slug}`}>
                  <div className="relative aspect-[2/3] overflow-hidden rounded-lg bg-neutral-800">
                    <Image src={m.thumbnail_url} alt={m.title} fill className="object-cover" />
                  </div>
                  <p className="mt-2 truncate text-sm text-neutral-200">{m.title}</p>
                </Link>
              ))}
            </div>
          </>
        )}

        {!series.length && !movies.length && (
          <p className="text-sm text-neutral-500">Noch nichts in dieser Kategorie.</p>
        )}
      </div>
    </div>
  );
}
