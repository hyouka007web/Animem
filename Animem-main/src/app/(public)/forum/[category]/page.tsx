import Link from "next/link";
import { notFound } from "next/navigation";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { enrichWithProfiles } from "@/lib/pocketbase/enrich";
import NewThreadForm from "@/components/forum/NewThreadForm";

export default async function ForumCategoryPage({ params }: { params: { category: string } }) {
  const pb = await createAdminClient();

  const category = await pb
    .collection(COL.forumCategories)
    .getFirstListItem(pb.filter("slug = {:slug}", { slug: params.category }))
    .catch(() => null);
  if (!category) notFound();

  const threadsRaw = await pb.collection(COL.forumThreads).getFullList({
    filter: pb.filter("category_id = {:id}", { id: category!.id }),
    sort: "-is_pinned,-created",
  });
  const threads = await enrichWithProfiles(pb, threadsRaw, "user_id");

  return (
    <div className="min-h-screen bg-neutral-950 px-4 py-8 text-white">
      <div className="mx-auto max-w-3xl">
        <h1 className="mb-1 text-2xl font-bold">{category!.name}</h1>
        <p className="mb-6 text-sm text-neutral-400">{category!.description}</p>

        <NewThreadForm categoryId={category!.id} categorySlug={category!.slug} />

        <div className="mt-6 space-y-2">
          {threads.map((t: any) => (
            <Link
              key={t.id}
              href={`/forum/${params.category}/${t.id}`}
              className="flex items-center justify-between rounded-lg border border-white/10 bg-neutral-900/60 px-4 py-3 hover:bg-neutral-900"
            >
              <span>
                {t.is_pinned && "📌 "}
                {t.title}
              </span>
              <span className="text-xs text-neutral-500">von {t.user?.username}</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
