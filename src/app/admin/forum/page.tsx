import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";

export default async function AdminForumPage() {
  const pb = await createAdminClient();
  const threadsRaw = await pb.collection(COL.forumThreads).getFullList({ sort: "-created" });

  const threads = await Promise.all(
    threadsRaw.slice(0, 50).map(async (t) => {
      let category: any = null;
      let user: any = null;
      try {
        category = await pb.collection(COL.forumCategories).getOne(t.category_id);
      } catch {}
      try {
        user = await pb.collection(COL.users).getOne(t.user_id);
      } catch {}
      return { ...t, category, user };
    })
  );

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Forum-Moderation</h1>
      <div className="overflow-hidden rounded-xl border border-white/10">
        <table className="w-full text-left text-sm">
          <thead className="bg-white/5 text-neutral-400">
            <tr>
              <th className="px-4 py-3 font-medium">Titel</th>
              <th className="px-4 py-3 font-medium">Kategorie</th>
              <th className="px-4 py-3 font-medium">Von</th>
              <th className="px-4 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {threads.map((t: any) => (
              <tr key={t.id}>
                <td className="px-4 py-3">{t.title}</td>
                <td className="px-4 py-3 text-neutral-400">{t.category?.name}</td>
                <td className="px-4 py-3 text-neutral-400">{t.user?.username}</td>
                <td className="px-4 py-3 text-neutral-400">
                  {t.is_locked ? "Gesperrt" : t.is_pinned ? "Angepinnt" : "Normal"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-neutral-500">
        Volle Moderationsfunktionen (Sperren/Pinnen/Löschen direkt hier) folgen als nächster Ausbauschritt.
      </p>
    </div>
  );
}
