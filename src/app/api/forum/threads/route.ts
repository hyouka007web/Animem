import { NextRequest } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { enrichWithProfiles } from "@/lib/pocketbase/enrich";
import { forumThreadSchema } from "@/lib/validation";
import { noStoreJson, rateLimit, rateLimitResponse, safeError } from "@/lib/security";

export async function GET(req: NextRequest) {
  const categorySlug = req.nextUrl.searchParams.get("category");
  const page = Math.max(1, Number(req.nextUrl.searchParams.get("page") || 1));
  const perPage = Math.min(50, Math.max(1, Number(req.nextUrl.searchParams.get("limit") || 25)));
  const pb = await createAdminClient();

  let filter = "";
  if (categorySlug) {
    const category = await pb.collection(COL.forumCategories)
      .getFirstListItem(pb.filter("slug = {:slug}", { slug: categorySlug })).catch(() => null);
    if (!category) return noStoreJson([]);
    filter = pb.filter("category_id = {:id}", { id: category.id });
  }

  const result = await pb.collection(COL.forumThreads).getList(page, perPage, { filter, sort: "-is_pinned,-created" });
  const withUsers = await enrichWithProfiles(pb, result.items, "user_id");

  const withCounts = await Promise.all(withUsers.map(async (thread: any) => {
    const posts = await pb.collection(COL.forumPosts).getList(1, 1, {
      filter: pb.filter("thread_id = {:id}", { id: thread.id }),
    });
    return { ...thread, posts: [{ count: posts.totalItems }] };
  }));

  return noStoreJson({ items: withCounts, page: result.page, perPage: result.perPage, totalItems: result.totalItems, totalPages: result.totalPages });
}

export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return noStoreJson({ error: "Nicht angemeldet" }, { status: 401 });
  const limit = rateLimit(req, `forum-thread:${user.id}`, 3, 10 * 60_000);
  if (!limit.allowed) return rateLimitResponse(limit.retryAfter);

  const parsed = forumThreadSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return noStoreJson({ error: "Ungültiger Thread." }, { status: 400 });

  const pb = await createAdminClient();
  try {
    const category = await pb.collection(COL.forumCategories).getOne(parsed.data.categoryId);
    if (!category) return noStoreJson({ error: "Kategorie nicht gefunden" }, { status: 404 });

    const thread = await pb.collection(COL.forumThreads).create({
      category_id: parsed.data.categoryId,
      user_id: user.id,
      title: parsed.data.title,
      is_pinned: false,
      is_locked: false,
    });

    try {
      await pb.collection(COL.forumPosts).create({ thread_id: thread.id, user_id: user.id, content: parsed.data.content });
    } catch (error) {
      await pb.collection(COL.forumThreads).delete(thread.id).catch(() => undefined);
      throw error;
    }

    return noStoreJson(thread, { status: 201 });
  } catch (error) {
    return noStoreJson({ error: safeError(error, "Thread konnte nicht erstellt werden.") }, { status: 500 });
  }
}
