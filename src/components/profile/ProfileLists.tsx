import Image from "next/image";
import Link from "next/link";

interface Poster {
  slug: string;
  title: string;
  thumbnail_url: string;
}

export default function ProfileLists({
  watchlist,
  subscriptions,
  collections,
}: {
  watchlist: { id: string; series: Poster | null; movie: Poster | null }[];
  subscriptions: { id: string; series: Poster | null }[];
  collections: { id: string; title: string; description: string | null }[];
}) {
  return (
    <div className="space-y-8">
      <Section title="Watchlist">
        <Grid>
          {watchlist.map((item) => {
            const target = item.series ?? item.movie;
            if (!target) return null;
            const href = item.series ? `/series/${target.slug}` : `/movies/${target.slug}`;
            return <PosterCard key={item.id} href={href} title={target.title} thumb={target.thumbnail_url} />;
          })}
          {!watchlist.length && <Empty text="Noch nichts auf der Watchlist." />}
        </Grid>
      </Section>

      <Section title="Abonnierte Serien">
        <Grid>
          {subscriptions.map((item) =>
            item.series ? (
              <PosterCard key={item.id} href={`/series/${item.series.slug}`} title={item.series.title} thumb={item.series.thumbnail_url} />
            ) : null
          )}
          {!subscriptions.length && <Empty text="Noch keine Serie abonniert." />}
        </Grid>
      </Section>

      <Section title="Sammlungen">
        <div className="space-y-2">
          {collections.map((c) => (
            <div key={c.id} className="rounded-lg border border-white/10 bg-neutral-900/60 px-4 py-3">
              <p className="text-sm font-medium">{c.title}</p>
              {c.description && <p className="text-xs text-neutral-500">{c.description}</p>}
            </div>
          ))}
          {!collections.length && <Empty text="Noch keine Sammlung erstellt." />}
        </div>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      {children}
    </div>
  );
}

function Grid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-6">{children}</div>;
}

function PosterCard({ href, title, thumb }: { href: string; title: string; thumb: string }) {
  return (
    <Link href={href}>
      <div className="relative aspect-[2/3] overflow-hidden rounded-lg bg-neutral-800">
        <Image src={thumb} alt={title} fill className="object-cover" />
      </div>
      <p className="mt-1 truncate text-xs text-neutral-300">{title}</p>
    </Link>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="text-sm text-neutral-500">{text}</p>;
}
