import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";

export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "Nicht angemeldet" }, { status: 401 });

  const { threadId, content } = await req.json();
  if (!threadId || !content) {
    return NextResponse.json({ error: "Inhalt fehlt" }, { status: 400 });
  }

  const pb = await createAdminClient();

  let thread;
  try {
    thread = await pb.collection(COL.forumThreads).getOne(threadId);
  } catch {
    return NextResponse.json({ error: "Thread nicht gefunden" }, { status: 404 });
  }
  if (thread.is_locked) {
    return NextResponse.json({ error: "Dieser Thread ist gesperrt" }, { status: 403 });
  }

  try {
    const post = await pb.collection(COL.forumPosts).create({
      thread_id: threadId,
      user_id: user.id,
      content,
    });

    let profile: any = null;
    try {
      profile = await pb.collection(COL.users).getOne(user.id);
    } catch {}

    return NextResponse.json(
      { ...post, user: profile ? { username: profile.username, avatar_url: profile.avatar_url ?? null } : null },
      { status: 201 }
    );
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
