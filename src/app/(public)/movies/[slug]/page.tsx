import { notFound } from "next/navigation";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import EmbedPlayer from "@/components/player/EmbedPlayer";
import RatingWidget from "@/components/series/RatingWidget";

export default async function MovieDetailPage({ params }: { params: { slug: string } }) {
  const pb = await createAdminClient();
  const user = await getCurrentUser();

  const movie = await pb
    .collection(COL.movies)
    .getFirstListItem(pb.filter("slug = {:slug} && status = \"PUBLISHED\"", { slug: params.slug }))
    .catch(() => null);
  if (!movie) notFound();

  let myRating: number | null = null;
  if (user) {
    const ratingDoc = await pb
      .collection(COL.ratings)
      .getFirstListItem(
        pb.filter("user_id = {:uid} && movie_id = {:mid} && target_type = \"MOVIE\"", {
          uid: user.id,
          mid: movie!.id,
        })
      )
      .catch(() => null);
    myRating = ratingDoc?.value ?? null;

    const historyDoc = await pb
      .collection(COL.watchHistory)
      .getFirstListItem(pb.filter("user_id = {:uid} && movie_id = {:mid}", { uid: user.id, mid: movie!.id }))
      .catch(() => null);
    if (historyDoc) {
      await pb.collection(COL.watchHistory).update(historyDoc.id, {});
    } else {
      await pb.collection(COL.watchHistory).create({
        user_id: user.id,
        target_type: "MOVIE",
        movie_id: movie!.id,
        progress_sec: 0,
      });
    }
  }

  return (
    <div className="min-h-screen bg-neutral-950 px-4 py-6 text-white">
      <div className="mx-auto max-w-4xl">
        <h1 className="text-xl font-bold">{movie!.title}</h1>
        <p className="mt-1 text-sm text-neutral-400">
          ⭐ {Number(movie!.avg_rating).toFixed(1)} · {movie!.ratings_count} Bewertungen
        </p>

        <div className="mt-4">
          <EmbedPlayer embedUrl={movie!.embed_url} title={movie!.title} />
        </div>

        <div className="mt-4">
          {user ? <RatingWidget targetType="MOVIE" movieId={movie!.id} initialValue={myRating} /> : null}
        </div>

        {movie!.description && <p className="mt-4 text-sm text-neutral-300">{movie!.description}</p>}
      </div>
    </div>
  );
}
