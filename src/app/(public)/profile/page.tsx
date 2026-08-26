import { redirect } from "next/navigation";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { enrichWithTargets } from "@/lib/pocketbase/enrich";
import ProfileHeader from "@/components/profile/ProfileHeader";
import FavoritesPicker from "@/components/profile/FavoritesPicker";
import ProfileLists from "@/components/profile/ProfileLists";

export default async function ProfilePage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  const pb = await createAdminClient();
  const uidFilter = pb.filter("user_id = {:uid}", { uid: user.id });

  const [profile, favoritesRaw, allSeries, allMovies, watchlistRaw, subscriptionsRaw, collections] =
    await Promise.all([
      pb.collection(COL.users).getOne(user.id),
      pb.collection(COL.profileFavorites).getFullList({ filter: uidFilter, sort: "rank" }),
      pb.collection(COL.series).getFullList({ filter: 'status = "PUBLISHED"', sort: "title" }),
      pb.collection(COL.movies).getFullList({ filter: 'status = "PUBLISHED"', sort: "title" }),
      pb.collection(COL.watchlistItems).getFullList({ filter: uidFilter }),
      pb.collection(COL.subscriptions).getFullList({ filter: uidFilter }),
      pb.collection(COL.userCollections).getFullList({ filter: uidFilter }),
    ]);

  const favorites = await enrichWithTargets(pb, favoritesRaw);
  const watchlist = await enrichWithTargets(pb, watchlistRaw);
  const subscriptions = await enrichWithTargets(pb, subscriptionsRaw);

  return (
    <div className="min-h-screen bg-neutral-950 px-4 py-8 text-white">
      <div className="mx-auto max-w-4xl">
        <ProfileHeader
          userId={user.id}
          username={profile?.username ?? user.username}
          displayName={profile?.display_name ?? null}
          role={profile?.role ?? user.role}
          avatarUrl={profile?.avatar_url ?? null}
          bio={profile?.bio ?? null}
        />

        <FavoritesPicker
          favorites={favorites as any}
          allSeries={allSeries.map((s) => ({ id: s.id, title: s.title }))}
          allMovies={allMovies.map((m) => ({ id: m.id, title: m.title }))}
        />

        <ProfileLists
          watchlist={watchlist as any}
          subscriptions={subscriptions as any}
          collections={collections.map((c: any) => ({ id: c.id, title: c.title, description: c.description }))}
        />
      </div>
    </div>
  );
}
