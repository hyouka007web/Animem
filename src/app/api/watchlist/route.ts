import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { enrichWithTargets } from "@/lib/pocketbase/enrich";

export async function GET() {
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "Nicht angemeldet" }, { status: 401 });

  const pb = await createAdminClient();
  const raw = await pb.collection(COL.watchlistItems).getFullList({
    filter: pb.filter("user_id = {:uid}", { uid: user.id }),
    sort: "-created",
  });

  const items = await enrichWithTargets(pb, raw);
  return NextResponse.json(items);
}

export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "Nicht angemeldet" }, { status: 401 });

  const { seriesId, movieId } = await req.json();
  const pb = await createAdminClient();

  try {
    const data = await pb.collection(COL.watchlistItems).create({
      user_id: user.id,
      series_id: seriesId ?? null,
      movie_id: movieId ?? null,
    });
    return NextResponse.json(data, { status: 201 });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function DELETE(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "Nicht angemeldet" }, { status: 401 });

  const { seriesId, movieId } = await req.json();
  const pb = await createAdminClient();

  const field = seriesId ? "series_id" : "movie_id";
  const value = seriesId ?? movieId;

  const existing = await pb
    .collection(COL.watchlistItems)
    .getFullList({ filter: pb.filter("user_id = {:uid} && " + field + " = {:v}", { uid: user.id, v: value }) });

  for (const doc of existing) {
    await pb.collection(COL.watchlistItems).delete(doc.id);
  }

  return NextResponse.json({ success: true });
}
