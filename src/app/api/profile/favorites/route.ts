import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";

// Sieger-Treppchen-Platz (1-3) setzen oder ersetzen
export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "Nicht angemeldet" }, { status: 401 });

  const { rank, seriesId, movieId } = await req.json();
  if (![1, 2, 3].includes(rank)) {
    return NextResponse.json({ error: "Ungültiger Platz" }, { status: 400 });
  }

  const pb = await createAdminClient();

  try {
    const existing = await pb
      .collection(COL.profileFavorites)
      .getFirstListItem(pb.filter("user_id = {:uid} && rank = {:r}", { uid: user.id, r: rank }))
      .catch(() => null);

    let data;
    if (existing) {
      data = await pb.collection(COL.profileFavorites).update(existing.id, {
        series_id: seriesId ?? null,
        movie_id: movieId ?? null,
      });
    } else {
      data = await pb.collection(COL.profileFavorites).create({
        user_id: user.id,
        rank,
        series_id: seriesId ?? null,
        movie_id: movieId ?? null,
      });
    }
    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function DELETE(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "Nicht angemeldet" }, { status: 401 });

  const { rank } = await req.json();
  const pb = await createAdminClient();

  const existing = await pb
    .collection(COL.profileFavorites)
    .getFullList({ filter: pb.filter("user_id = {:uid} && rank = {:r}", { uid: user.id, r: rank }) });

  for (const doc of existing) {
    await pb.collection(COL.profileFavorites).delete(doc.id);
  }

  return NextResponse.json({ success: true });
}
