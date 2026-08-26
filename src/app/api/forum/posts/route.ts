import { NextRequest } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { forumPostSchema } from "@/lib/validation";
import { noStoreJson, rateLimit, rateLimitResponse, safeError } from "@/lib/security";

export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return noStoreJson({ error: "Nicht angemeldet" }, { status: 401 });
  const limit = rateLimit(req, `forum-post:${user.id}`, 10, 60_000);
  if (!limit.allowed) return rateLimitResponse(limit.retryAfter);

  const parsed = forumPostSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return noStoreJson({ error: "Ungültiger Beitrag." }, { status: 400 });

  const pb = await createAdminClient();
  let thread;
  try {
    thread = await pb.collection(COL.forumThreads).getOne(parsed.data.threadId);
  } catch {
    return noStoreJson({ error: "Thread nicht gefunden" }, { status: 404 });
  }
  if (thread.is_locked) return noStoreJson({ error: "Dieser Thread ist gesperrt" }, { status: 403 });

  try {
    const post = await pb.collection(COL.forumPosts).create({
      thread_id: thread.id,
      user_id: user.id,
      content: parsed.data.content,
    });

    let profile: any = null;
    try { profile = await pb.collection(COL.users).getOne(user.id); } catch {}

    return noStoreJson({
      ...post,
      user: profile ? { username: profile.username, avatar_url: profile.avatar_url ?? null } : null,
    }, { status: 201 });
  } catch (error) {
    return noStoreJson({ error: safeError(error, "Beitrag konnte nicht erstellt werden.") }, { status: 500 });
  }
}
