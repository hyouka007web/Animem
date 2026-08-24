import Link from "next/link";
import { notFound } from "next/navigation";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import EmbedPlayer from "@/components/player/EmbedPlayer";
import RatingWidget from "@/components/series/RatingWidget";

interface Params {
  params: { slug: string; season: string; episode: string };
}

export default async function EpisodePage({ params }: Params) {
  const pb = await createAdminClient();
  const user = await getCurrentUser();

  const series = await pb
    .collection(COL.series)
    .getFirstListItem(pb.filter("slug = {:slug}", { slug: params.slug }))
    .catch(() => null);
  if (!series) notFound();

  const season = await pb
    .collection(COL.seasons)
    .getFirstListItem(
      pb.filter("series_id = {:sid} && number = {:n}", { sid: series!.id, n: Number(params.season) })
    )
    .catch(() => null);
  if (!season) notFound();

  const episodes = await pb
    .collection(COL.episodes)
    .getFullList({ filter: pb.filter("season_id = {:id}", { id: season!.id }) });
  const episode = episodes.find((e) => e.number === Number(params.episode));

  if (!episode || episode.status !== "PUBLISHED") notFound();

  let myRating: number | null = null;
  if (user) {
    const ratingDoc = await pb
      .collection(COL.ratings)
      .getFirstListItem(
        pb.filter("user_id = {:uid} && episode_id = {:eid} && target_type = \"EPISODE\"", {
          uid: user.id,
          eid: episode.id,
        })
      )
      .catch(() => null);
    myRating = ratingDoc?.value ?? null;

    // Verlauf protokollieren (find-or-create)
    const historyDoc = await pb
      .collection(COL.watchHistory)
      .getFirstListItem(pb.filter("user_id = {:uid} && episode_id = {:eid}", { uid: user.id, eid: episode.id }))
      .catch(() => null);
    if (historyDoc) {
      await pb.collection(COL.watchHistory).update(historyDoc.id, {});
    } else {
      await pb.collection(COL.watchHistory).create({
        user_id: user.id,
        target_type: "EPISODE",
        episode_id: episode.id,
        progress_sec: 0,
      });
    }
  }

  const nextEpisode = episodes.find((e) => e.number === episode.number + 1);

  return (
    <div className="min-h-screen bg-neutral-950 px-4 py-6 text-white">
      <div className="mx-auto max-w-4xl">
        <Link href={`/series/${params.slug}`} className="text-sm text-neutral-400 hover:text-white">
          ← {series!.title}
        </Link>

        <h1 className="mt-2 text-xl font-bold">
          S{season!.number} · E{episode.number} — {episode.title}
        </h1>

        <div className="mt-4">
          <EmbedPlayer embedUrl={episode.embed_url} title={episode.title} />
        </div>

        <div className="mt-4 flex items-center justify-between">
          {user ? (
            <RatingWidget targetType="EPISODE" episodeId={episode.id} initialValue={myRating} />
          ) : (
            <span />
          )}

          {nextEpisode && (
            <Link
              href={`/series/${params.slug}/s/${season!.number}/e/${nextEpisode.number}`}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500"
            >
              Nächste Episode →
            </Link>
          )}
        </div>

        {episode.description && (
          <p className="mt-4 text-sm text-neutral-300">{episode.description}</p>
        )}
      </div>
    </div>
  );
}
