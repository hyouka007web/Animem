import Link from "next/link";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";

export default async function CategoriesPage() {
  const pb = await createAdminClient();
  const genres = await pb.collection(COL.genres).getFullList({ sort: "name" });

  return (
    <div className="min-h-screen bg-neutral-950 px-4 py-8 text-white">
      <div className="mx-auto max-w-4xl">
        <h1 className="mb-6 text-2xl font-bold">Kategorien</h1>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {genres.map((g) => (
            <Link
              key={g.id}
              href={`/genres/${g.slug}`}
              className="flex aspect-video items-center justify-center rounded-xl border border-white/10 bg-gradient-to-br from-indigo-600/30 to-neutral-900 p-4 text-center font-semibold hover:from-indigo-600/50"
            >
              {g.name}
            </Link>
          ))}
          {!genres.length && (
            <p className="col-span-full text-sm text-neutral-500">
              Noch keine Kategorien angelegt — Admins können beim Erstellen einer Serie/eines Films Genres vergeben.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
