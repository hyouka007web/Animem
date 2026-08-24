import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { can, assignableRoles, canManageTargetRole, type Role } from "@/lib/permissions";

export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
  const actor = await getCurrentUser();
  if (!actor || !can.manageAdmins(actor.role)) {
    return NextResponse.json({ error: "Nicht berechtigt" }, { status: 403 });
  }

  // Niemand darf die eigene Rolle über dieses Menü ändern — auch der Owner nicht
  if (params.id === actor.id) {
    return NextResponse.json({ error: "Du kannst deine eigene Rolle nicht ändern." }, { status: 403 });
  }

  const { role } = (await req.json()) as { role: Role };
  const pb = await createAdminClient();

  let target;
  try {
    target = await pb.collection(COL.users).getOne(params.id);
  } catch {
    return NextResponse.json({ error: "Nutzer nicht gefunden" }, { status: 404 });
  }

  // Darf der Handelnde diesen Nutzer überhaupt anfassen? (Head Admin z.B. nicht bei Head Admin/Owner)
  if (!canManageTargetRole(actor.role, target.role as Role)) {
    return NextResponse.json({ error: "Diese Rolle darfst du nicht bearbeiten." }, { status: 403 });
  }

  // Darf der Handelnde genau DIESE neue Rolle überhaupt vergeben?
  if (!assignableRoles(actor.role).includes(role)) {
    return NextResponse.json({ error: "Diese Rolle darfst du nicht vergeben." }, { status: 403 });
  }

  try {
    const data = await pb.collection(COL.users).update(params.id, { role });
    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
