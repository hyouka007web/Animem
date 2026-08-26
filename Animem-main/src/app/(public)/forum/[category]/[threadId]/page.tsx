import { notFound } from "next/navigation";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { enrichWithProfiles } from "@/lib/pocketbase/enrich";
import ReplyForm from "@/components/forum/ReplyForm";
import UserMention from "@/components/shared/UserMention";
import MentionText from "@/components/shared/MentionText";

export default async function ThreadPage({
  params,
}: {
  params: { category: string; threadId: string };
}) {
  const pb = await createAdminClient();
  const user = await getCurrentUser();

  let thread;
  try {
    thread = await pb.collection(COL.forumThreads).getOne(params.threadId);
  } catch {
    notFound();
  }

  let threadAuthor: any = null;
  try {
    threadAuthor = await pb.collection(COL.users).getOne(thread!.user_id);
  } catch {}

  const postsRaw = await pb.collection(COL.forumPosts).getFullList({
    filter: pb.filter("thread_id = {:id}", { id: params.threadId }),
    sort: "created",
  });
  const posts = await enrichWithProfiles(pb, postsRaw, "user_id");

  return (
    <div className="min-h-screen bg-neutral-950 px-4 py-8 text-white">
      <div className="mx-auto max-w-3xl">
        <h1 className="mb-1 text-xl font-bold">{thread!.title}</h1>
        <p className="mb-6 text-sm text-neutral-500">
          gestartet von <UserMention username={threadAuthor?.username ?? ""} />
        </p>

        <div className="space-y-3">
          {posts.map((post: any) => (
            <div key={post.id} className="rounded-lg border border-white/10 bg-neutral-900/60 p-4">
              <p className="mb-1 text-xs font-medium">
                <UserMention username={post.user?.username ?? ""} className="text-indigo-400" />
              </p>
              <p className="text-sm text-neutral-200 whitespace-pre-wrap">
                <MentionText text={post.content} />
              </p>
            </div>
          ))}
        </div>

        {thread!.is_locked ? (
          <p className="mt-4 text-sm text-neutral-500">Dieser Thread ist gesperrt.</p>
        ) : user ? (
          <ReplyForm threadId={thread!.id} />
        ) : (
          <p className="mt-4 text-sm text-neutral-500">Melde dich an, um zu antworten.</p>
        )}
      </div>
    </div>
  );
}
