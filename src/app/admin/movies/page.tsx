import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import MovieTable from "@/components/admin/MovieTable";

export default async function AdminMoviesPage() {
  const pb = await createAdminClient();
  const movies = await pb.collection(COL.movies).getFullList({ sort: "-created" });

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Filme verwalten</h1>
      <MovieTable initialMovies={movies as any} />
    </div>
  );
}
