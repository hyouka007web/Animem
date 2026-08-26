import Link from "next/link";
import { getCurrentUser } from "@/lib/auth";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { can } from "@/lib/permissions";
import MobileNavDrawer from "./MobileNavDrawer";
import Logo from "@/components/shared/Logo";

export default async function Navbar() {
  const user = await getCurrentUser();

  let watchlistCount = 0;
  let subscriptionsCount = 0;

  if (user) {
    const pb = await createAdminClient();
    const uidFilter = pb.filter("user_id = {:uid}", { uid: user.id });
    const [watchlist, subscriptions] = await Promise.all([
      pb.collection(COL.watchlistItems).getList(1, 1, { filter: uidFilter }),
      pb.collection(COL.subscriptions).getList(1, 1, { filter: uidFilter }),
    ]);
    watchlistCount = watchlist.totalItems;
    subscriptionsCount = subscriptions.totalItems;
  }

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-midnight-deep/90 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link href="/">
          <Logo />
        </Link>

        <MobileNavDrawer
          user={
            user
              ? { username: user.username, role: user.role, isStaff: can.manageContent(user.role) }
              : null
          }
          counts={{ watchlist: watchlistCount, subscriptions: subscriptionsCount }}
        />
      </div>
    </header>
  );
}
