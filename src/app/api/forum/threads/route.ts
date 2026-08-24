import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { enrichWithProfiles } from "@/lib/pocketbase/enrich";

export async function GET(req: NextRequest) {
  const categorySlug = req.nextUrl.searchParams.get("category");
  const pb = await createAdminClient();

  let filter = "";
  if (categorySlug) {
    const category = await pb
      .collection(COL.forumCategories)
      .getFirstListItem(pb.filter("slug = {:slug}", { slug: categorySlug }))
      .catch(() => null);
    if (!category) return NextResponse.json([]);
    filter = pb.filter("category_id = {:id}", { id: category.id });
  }

  const raw = await pb.collection(COL.forumThreads).getFullList({ filter, sort: "-is_pinned,-created" });
  const withUsers = await enrichWithProfiles(pb, raw, "user_id");

  // Post-Anzahl pro Thread nachladen (ersetzt Supabase "posts:forum_posts(count)")
  const withCounts = await Promise.all(
    withUsers.map(async (thread: any) => {
      const posts = await pb.collection(COL.forumPosts).getList(1, 1, {
        filter: pb.filter("thread_id = {:id}", { id: thread.id }),
      });
      return { ...thread, posts: [{ count: posts.totalItems }] };
    })
  );

  return NextResponse.json(withCounts);
}

export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "Nicht angemeldet" }, { status: 401 });

  const { categoryId, title, content } = await req.json();
  if (!categoryId || !title || !content) {
    return NextResponse.json({ error: "Titel, Kategorie und Inhalt sind Pflichtfelder" }, { status: 400 });
  }

  const pb = await createAdminClient();

  let thread;
  try {
    thread = await pb.collection(COL.forumThreads).create({
      category_id: categoryId,
      user_id: user.id,
      title,
      is_pinned: false,
      is_locked: false,
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }

  await pb.collection(COL.forumPosts).create({
    thread_id: thread.id,
    user_id: user.id,
    content,
  });

  return NextResponse.json(thread, { status: 201 });
}
