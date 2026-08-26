import Link from "next/link";
import { MessagesSquare } from "lucide-react";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";

export default async function ForumOverviewPage() {
  const pb = await createAdminClient();
  const categories = await pb.collection(COL.forumCategories).getFullList({ sort: "order" });

  return (
    <div className="min-h-screen bg-neutral-950 px-4 py-8 text-white">
      <div className="mx-auto max-w-3xl">
        <h1 className="mb-6 text-2xl font-bold">Forum</h1>
        <div className="space-y-2">
          {categories.map((cat) => (
            <Link
              key={cat.id}
              href={`/forum/${cat.slug}`}
              className="flex items-center gap-3 rounded-xl border border-white/10 bg-neutral-900/60 p-4 hover:bg-neutral-900"
            >
              <MessagesSquare className="h-5 w-5 text-indigo-400" />
              <div>
                <p className="font-medium">{cat.name}</p>
                <p className="text-sm text-neutral-400">{cat.description}</p>
              </div>
            </Link>
          ))}
          {!categories.length && (
            <p className="text-sm text-neutral-500">Noch keine Forumskategorien angelegt.</p>
          )}
        </div>
      </div>
    </div>
  );
}
