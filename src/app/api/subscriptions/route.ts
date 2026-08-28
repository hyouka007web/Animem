import { NextRequest } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { enrichWithTargets } from "@/lib/pocketbase/enrich";
import { subscriptionSchema } from "@/lib/validation";
import { noStoreJson, rateLimit, rateLimitResponse, safeError } from "@/lib/security";

export async function GET() {
  const user = await getCurrentUser();
  if (!user) return noStoreJson({ error: "Nicht angemeldet" }, { status: 401 });
  const pb = await createAdminClient();
  const raw = await pb.collection(COL.subscriptions).getList(1, 200, { filter: pb.filter("user_id = {:uid}", { uid: user.id }), sort: "-created" });
  return noStoreJson(await enrichWithTargets(pb, raw.items));
}

export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return noStoreJson({ error: "Nicht angemeldet" }, { status: 401 });
  const limit = rateLimit(req, `subscriptions:${user.id}`, 30, 60_000);
  if (!limit.allowed) return rateLimitResponse(limit.retryAfter);
  const parsed = subscriptionSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return noStoreJson({ error: "Ungültige Serie." }, { status: 400 });
  const pb = await createAdminClient();
  try { await pb.collection(COL.series).getOne(parsed.data.seriesId); }
  catch { return noStoreJson({ error: "Serie nicht gefunden." }, { status: 404 }); }

  const existing = await pb.collection(COL.subscriptions).getFirstListItem(pb.filter("user_id = {:uid} && series_id = {:sid}", { uid: user.id, sid: parsed.data.seriesId })).catch(() => null);
  if (existing) return noStoreJson(existing);
  try {
    const data = await pb.collection(COL.subscriptions).create({ user_id: user.id, series_id: parsed.data.seriesId, notify_on_new_episode: true });
    return noStoreJson(data, { status: 201 });
  } catch (error) {
    const raced = await pb.collection(COL.subscriptions).getFirstListItem(pb.filter("user_id = {:uid} && series_id = {:sid}", { uid: user.id, sid: parsed.data.seriesId })).catch(() => null);
    if (raced) return noStoreJson(raced);
    return noStoreJson({ error: safeError(error, "Abo konnte nicht erstellt werden.") }, { status: 500 });
  }
}

export async function DELETE(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return noStoreJson({ error: "Nicht angemeldet" }, { status: 401 });
  const parsed = subscriptionSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return noStoreJson({ error: "Ungültige Serie." }, { status: 400 });
  const pb = await createAdminClient();
  const existing = await pb.collection(COL.subscriptions).getFullList({ filter: pb.filter("user_id = {:uid} && series_id = {:sid}", { uid: user.id, sid: parsed.data.seriesId }) });
  await Promise.all(existing.map((doc) => pb.collection(COL.subscriptions).delete(doc.id)));
  return noStoreJson({ success: true });
}
