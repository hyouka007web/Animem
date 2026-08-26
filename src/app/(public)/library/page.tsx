import Image from "next/image";
import Link from "next/link";
import { redirect } from "next/navigation";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { enrichWithTargets } from "@/lib/pocketbase/enrich";
import LibraryTabs from "@/components/library/LibraryTabs";

export default async function LibraryPage({
  searchParams,
}: {
  searchParams: { tab?: string };
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  const pb = await createAdminClient();
  const activeTab = searchParams.tab ?? "watchlist";
  const uidFilter = pb.filter("user_id = {:uid}", { uid: user.id });

  const [watchlistRaw, subscriptionsRaw, historyRaw, collections] = await Promise.all([
    pb.collection(COL.watchlistItems).getFullList({ filter: uidFilter, sort: "-created" }),
    pb.collection(COL.subscriptions).getFullList({ filter: uidFilter }),
    pb.collection(COL.watchHistory).getFullList({ filter: uidFilter, sort: "-updated" }),
    pb.collection(COL.userCollections).getFullList({ filter: uidFilter }),
  ]);

  const watchlist = await enrichWithTargets(pb, watchlistRaw);
  const subscriptions = await enrichWithTargets(pb, subscriptionsRaw);

  // Verlauf: Episoden brauchen den Umweg über Staffel -> Serie für Titel/Slug.
  const history = await Promise.all(
    historyRaw.slice(0, 30).map(async (h) => {
      if (h.movie_id) {
        try {
          const movie = await pb.collection(COL.movies).getOne(h.movie_id);
          return { id: h.id, watched_at: h.updated, isMovie: true, title: movie.title, href: `/movies/${movie.slug}` };
        } catch {
          return null;
        }
      }
      if (h.episode_id) {
        try {
          const episode = await pb.collection(COL.episodes).getOne(h.episode_id);
          const season = await pb.collection(COL.seasons).getOne(episode.season_id);
          const series = await pb.collection(COL.series).getOne(season.series_id);
          return {
            id: h.id,
            watched_at: h.updated,
            isMovie: false,
            title: `${series.title} — ${episode.title}`,
            href: `/series/${series.slug}`,
          };
        } catch {
          return null;
        }
      }
      return null;
    })
  );

  return (
    <div className="min-h-screen bg-neutral-950 px-4 py-8 text-white">
      <div className="mx-auto max-w-5xl">
        <h1 className="mb-6 text-2xl font-bold">Bibliothek</h1>

        <LibraryTabs active={activeTab} />

        {activeTab === "watchlist" && (
          <Grid>
            {watchlist.map((item: any) => {
              const target = item.series ?? item.movie;
              const href = item.series ? `/series/${target.slug}` : `/movies/${target.slug}`;
              return target ? <PosterCard key={item.id} href={href} title={target.title} thumb={target.thumbnail_url} /> : null;
            })}
            {!watchlist.length && <Empty text="Deine Watchlist ist noch leer." />}
          </Grid>
        )}

        {activeTab === "subscriptions" && (
          <Grid>
            {subscriptions.map((item: any) =>
              item.series ? (
                <PosterCard key={item.id} href={`/series/${item.series.slug}`} title={item.series.title} thumb={item.series.thumbnail_url} />
              ) : null
            )}
            {!subscriptions.length && <Empty text="Du hast noch keine Serien abonniert." />}
          </Grid>
        )}

        {activeTab === "history" && (
          <div className="space-y-2">
            {history.filter(Boolean).map((h: any) => (
              <Link
                key={h.id}
                href={h.href}
                className="flex items-center justify-between rounded-lg border border-white/10 bg-neutral-900/60 px-4 py-3 hover:bg-neutral-900"
              >
                <span className="text-sm">{h.title}</span>
                <span className="text-xs text-neutral-500">
                  {new Date(h.watched_at).toLocaleDateString("de-DE")}
                </span>
              </Link>
            ))}
            {!history.filter(Boolean).length && <Empty text="Noch kein Verlauf vorhanden." />}
          </div>
        )}

        {activeTab === "collections" && (
          <div className="space-y-2">
            {collections.map((c: any) => (
              <div key={c.id} className="rounded-lg border border-white/10 bg-neutral-900/60 px-4 py-3">
                <p className="text-sm font-medium">{c.title}</p>
                {c.description && <p className="text-xs text-neutral-500">{c.description}</p>}
              </div>
            ))}
            {!collections.length && <Empty text="Du hast noch keine Sammlung erstellt." />}
          </div>
        )}
      </div>
    </div>
  );
}

function Grid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">{children}</div>;
}

function PosterCard({ href, title, thumb }: { href: string; title: string; thumb: string }) {
  return (
    <Link href={href}>
      <div className="relative aspect-[2/3] overflow-hidden rounded-lg bg-neutral-800">
        <Image src={thumb} alt={title} fill className="object-cover" />
      </div>
      <p className="mt-2 truncate text-sm text-neutral-200">{title}</p>
    </Link>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="col-span-full py-8 text-center text-sm text-neutral-500">{text}</p>;
}
