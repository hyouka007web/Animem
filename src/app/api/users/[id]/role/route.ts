import { NextRequest } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { can, assignableRoles, canManageTargetRole, type Role } from "@/lib/permissions";
import { roleSchema } from "@/lib/validation";
import { noStoreJson, rateLimit, rateLimitResponse, safeError } from "@/lib/security";

export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
  const actor = await getCurrentUser();
  if (!actor || !can.manageAdmins(actor.role)) return noStoreJson({ error: "Nicht berechtigt" }, { status: 403 });
  if (params.id === actor.id) return noStoreJson({ error: "Du kannst deine eigene Rolle nicht ändern." }, { status: 403 });
  const limit = rateLimit(req, `role-change:${actor.id}`, 20, 10 * 60_000);
  if (!limit.allowed) return rateLimitResponse(limit.retryAfter);
  const parsed = roleSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return noStoreJson({ error: "Ungültige Rolle." }, { status: 400 });

  const pb = await createAdminClient();
  const target = await pb.collection(COL.users).getOne(params.id).catch(() => null);
  if (!target) return noStoreJson({ error: "Nutzer nicht gefunden" }, { status: 404 });
  if (!canManageTargetRole(actor.role, target.role as Role)) return noStoreJson({ error: "Diese Rolle darfst du nicht bearbeiten." }, { status: 403 });
  if (!assignableRoles(actor.role).includes(parsed.data.role as Role)) return noStoreJson({ error: "Diese Rolle darfst du nicht vergeben." }, { status: 403 });

  try {
    const data = await pb.collection(COL.users).update(params.id, { role: parsed.data.role });
    return noStoreJson(data);
  } catch (error) {
    return noStoreJson({ error: safeError(error, "Rolle konnte nicht geändert werden.") }, { status: 500 });
  }
}
