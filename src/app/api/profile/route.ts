import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";

// Eigenes Profil (Avatar, Bio) bearbeiten
export async function PATCH(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "Nicht angemeldet" }, { status: 401 });

  const { avatarUrl, bio, displayName } = await req.json();
  const pb = await createAdminClient();

  try {
    const data = await pb.collection(COL.users).update(user.id, {
      avatar_url: avatarUrl || "",
      bio: bio || "",
      display_name: displayName || "",
    });
    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
