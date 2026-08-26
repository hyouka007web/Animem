import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { UserCircle } from "lucide-react";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { enrichWithTargets } from "@/lib/pocketbase/enrich";

const ROLE_LABELS: Record<string, string> = {
  OWNER: "Owner",
  HEAD_ADMIN: "Head Admin",
  ADMIN: "Admin",
  USER: "User",
};

const RANK_RING: Record<number, string> = {
  1: "ring-2 ring-amber-400",
  2: "ring-2 ring-slate-300",
  3: "ring-2 ring-orange-400",
};

export default async function PublicProfilePage({ params }: { params: { username: string } }) {
  const pb = await createAdminClient();

  const profile = await pb
    .collection(COL.users)
    .getFirstListItem(pb.filter("username = {:u}", { u: params.username }))
    .catch(() => null);
  if (!profile) notFound();

  const favoritesRaw = await pb.collection(COL.profileFavorites).getFullList({
    filter: pb.filter("user_id = {:uid}", { uid: profile!.id }),
    sort: "rank",
  });
  const favorites = await enrichWithTargets(pb, favoritesRaw);

  return (
    <div className="min-h-screen bg-neutral-950 px-4 py-8 text-white">
      <div className="mx-auto max-w-3xl">
        <div className="mb-8 flex items-center gap-4 rounded-2xl border border-white/10 bg-neutral-900/60 p-6">
          {profile!.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={profile!.avatar_url} alt={profile!.username} className="h-20 w-20 rounded-full object-cover" />
          ) : (
            <UserCircle className="h-20 w-20 text-neutral-500" />
          )}
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold">{profile!.display_name || profile!.username}</h1>
              <span className="rounded-full bg-indigo-600/20 px-2 py-0.5 text-xs font-medium text-indigo-300">
                {ROLE_LABELS[profile!.role] ?? profile!.role}
              </span>
            </div>
            <p className="text-sm text-neutral-500">@{profile!.username}</p>
            {profile!.bio && <p className="mt-1 text-sm text-neutral-400">{profile!.bio}</p>}
          </div>
        </div>

        {!!favorites.length && (
          <div>
            <h2 className="mb-4 text-lg font-semibold">Sieger-Treppchen</h2>
            <div className="flex items-end justify-center gap-4">
              {[2, 1, 3].map((rank) => {
                const slot = (favorites as any[]).find((f) => f.rank === rank);
                const item = slot?.series ?? slot?.movie;
                if (!item) return null;
                const href = slot?.series ? `/series/${item.slug}` : `/movies/${item.slug}`;
                return (
                  <Link key={rank} href={href} className="flex flex-col items-center">
                    <div className={`relative h-24 w-16 overflow-hidden rounded-lg bg-neutral-800 ${RANK_RING[rank]}`}>
                      <Image src={item.thumbnail_url} alt={item.title} fill className="object-cover" />
                    </div>
                    <p className="mt-1 max-w-[4.5rem] truncate text-center text-xs text-neutral-300">
                      {item.title}
                    </p>
                  </Link>
                );
              })}
            </div>
          </div>
        )}

        {!favorites.length && (
          <p className="text-sm text-neutral-500">Noch kein Sieger-Treppchen ausgewählt.</p>
        )}
      </div>
    </div>
  );
}
