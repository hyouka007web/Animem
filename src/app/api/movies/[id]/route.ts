import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { can } from "@/lib/permissions";

export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
  const user = await getCurrentUser();
  if (!user || !can.manageContent(user.role)) {
    return NextResponse.json({ error: "Nicht berechtigt" }, { status: 403 });
  }

  const body = await req.json();
  const pb = await createAdminClient();

  try {
    const data = await pb.collection(COL.movies).update(params.id, {
      title: body.title,
      description: body.description || "",
      thumbnail_url: body.thumbnailUrl,
      banner_url: body.bannerUrl || "",
      embed_url: body.embedUrl,
      embed_provider: body.embedProvider || "",
      status: body.status,
    });
    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function DELETE(_req: NextRequest, { params }: { params: { id: string } }) {
  const user = await getCurrentUser();
  if (!user || !can.manageAdmins(user.role)) {
    return NextResponse.json({ error: "Nicht berechtigt" }, { status: 403 });
  }

  const pb = await createAdminClient();
  try {
    await pb.collection(COL.movies).delete(params.id);
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
  return NextResponse.json({ success: true });
}
