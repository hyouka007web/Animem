import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { enrichWithTargets } from "@/lib/pocketbase/enrich";

export async function GET() {
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "Nicht angemeldet" }, { status: 401 });

  const pb = await createAdminClient();
  const raw = await pb
    .collection(COL.subscriptions)
    .getFullList({ filter: pb.filter("user_id = {:uid}", { uid: user.id }) });

  const items = await enrichWithTargets(pb, raw);
  return NextResponse.json(items);
}

export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "Nicht angemeldet" }, { status: 401 });

  const { seriesId } = await req.json();
  const pb = await createAdminClient();

  try {
    const data = await pb.collection(COL.subscriptions).create({
      user_id: user.id,
      series_id: seriesId,
      notify_on_new_episode: true,
    });
    return NextResponse.json(data, { status: 201 });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function DELETE(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "Nicht angemeldet" }, { status: 401 });

  const { seriesId } = await req.json();
  const pb = await createAdminClient();

  const existing = await pb.collection(COL.subscriptions).getFullList({
    filter: pb.filter("user_id = {:uid} && series_id = {:sid}", { uid: user.id, sid: seriesId }),
  });

  for (const doc of existing) {
    await pb.collection(COL.subscriptions).delete(doc.id);
  }

  return NextResponse.json({ success: true });
}
