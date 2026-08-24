import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Star } from "lucide-react";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import SubscribeButton from "@/components/series/SubscribeButton";
import RatingWidget from "@/components/series/RatingWidget";

export default async function SeriesDetailPage({ params }: { params: { slug: string } }) {
  const pb = await createAdminClient();
  const user = await getCurrentUser();

  const series = await pb
    .collection(COL.series)
    .getFirstListItem(pb.filter("slug = {:slug}", { slug: params.slug }))
    .catch(() => null);
  if (!series) notFound();

  const [seasonsRaw, tags] = await Promise.all([
    pb.collection(COL.seasons).getFullList({ filter: pb.filter("series_id = {:id}", { id: series!.id }) }),
    Promise.all(
      ((series!.tag_ids as string[]) ?? []).map(async (id) => {
        try {
          return await pb.collection(COL.tags).getOne(id);
        } catch {
          return null;
        }
      })
    ),
  ]);

  const seasons = await Promise.all(
    seasonsRaw
      .sort((a, b) => a.number - b.number)
      .map(async (season) => {
        const episodes = await pb
          .collection(COL.episodes)
          .getFullList({ filter: pb.filter("season_id = {:id}", { id: season.id }) });
        return { ...season, episodes };
      })
  );

  let myRating: number | null = null;
  let isSubscribed = false;

  if (user) {
    const [ratingDoc, subDoc] = await Promise.all([
      pb
        .collection(COL.ratings)
        .getFirstListItem(
          pb.filter("user_id = {:uid} && series_id = {:sid} && target_type = \"SERIES\"", {
            uid: user.id,
            sid: series!.id,
          })
        )
        .catch(() => null),
      pb
        .collection(COL.subscriptions)
        .getFirstListItem(pb.filter("user_id = {:uid} && series_id = {:sid}", { uid: user.id, sid: series!.id }))
        .catch(() => null),
    ]);
    myRating = ratingDoc?.value ?? null;
    isSubscribed = !!subDoc;
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-white">
      {series!.banner_url && (
        <div className="relative h-56 w-full md:h-72">
          <Image src={series!.banner_url} alt={series!.title} fill className="object-cover opacity-40" />
          <div className="absolute inset-0 bg-gradient-to-t from-neutral-950 to-transparent" />
        </div>
      )}

      <div className="mx-auto -mt-16 max-w-5xl px-4 pb-12">
        <div className="flex flex-col gap-6 md:flex-row">
          <div className="relative h-56 w-40 shrink-0 overflow-hidden rounded-xl bg-neutral-800">
            <Image src={series!.thumbnail_url} alt={series!.title} fill className="object-cover" />
          </div>

          <div className="flex-1">
            <h1 className="text-2xl font-bold md:text-3xl">{series!.title}</h1>
            <div className="mt-2 flex items-center gap-2 text-sm text-neutral-300">
              <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
              {Number(series!.avg_rating).toFixed(1)} · {series!.ratings_count} Bewertungen
            </div>
            <p className="mt-4 max-w-2xl text-sm text-neutral-300">{series!.description}</p>

            {!!tags.filter(Boolean).length && (
              <div className="mt-3 flex flex-wrap gap-2">
                {tags.filter(Boolean).map((t: any) => (
                  <Link
                    key={t.slug}
                    href={`/tags/${t.slug}`}
                    className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-neutral-300 hover:bg-white/10"
                  >
                    #{t.name}
                  </Link>
                ))}
              </div>
            )}

            <div className="mt-4 flex flex-wrap items-center gap-3">
              {user ? (
                <>
                  <SubscribeButton seriesId={series!.id} initiallySubscribed={isSubscribed} />
                  <RatingWidget targetType="SERIES" seriesId={series!.id} initialValue={myRating} />
                </>
              ) : (
                <Link href="/login" className="text-sm text-indigo-400 hover:text-indigo-300">
                  Anmelden, um zu bewerten oder zu abonnieren
                </Link>
              )}
            </div>
          </div>
        </div>

        <div className="mt-10 space-y-8">
          {seasons.map((season: any) => (
            <div key={season.id}>
              <h2 className="mb-3 text-lg font-semibold">
                Staffel {season.number}
                {season.title ? ` — ${season.title}` : ""}
              </h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
                {season.episodes
                  .filter((ep: any) => ep.status === "PUBLISHED")
                  .sort((a: any, b: any) => a.number - b.number)
                  .map((ep: any) => (
                    <Link
                      key={ep.id}
                      href={`/series/${params.slug}/s/${season.number}/e/${ep.number}`}
                      className="group"
                    >
                      <div className="relative aspect-video overflow-hidden rounded-lg bg-neutral-800">
                        <Image
                          src={series!.thumbnail_url}
                          alt={ep.title}
                          fill
                          className="object-cover opacity-70 transition group-hover:scale-105 group-hover:opacity-100"
                        />
                        <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                          <span className="text-lg font-bold text-white">E{ep.number}</span>
                        </div>
                      </div>
                      <p className="mt-1 truncate text-xs text-neutral-300">
                        {ep.number}. {ep.title}
                      </p>
                    </Link>
                  ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
