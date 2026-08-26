import { NextRequest } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { profileSchema } from "@/lib/validation";
import { noStoreJson, rateLimit, rateLimitResponse, safeError } from "@/lib/security";

export async function PATCH(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return noStoreJson({ error: "Nicht angemeldet" }, { status: 401 });
  const limit = rateLimit(req, `profile:${user.id}`, 10, 10 * 60_000);
  if (!limit.allowed) return rateLimitResponse(limit.retryAfter);
  const parsed = profileSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return noStoreJson({ error: "Ungültige Profildaten." }, { status: 400 });

  const pb = await createAdminClient();
  try {
    const data = await pb.collection(COL.users).update(user.id, {
      avatar_url: parsed.data.avatarUrl,
      bio: parsed.data.bio,
      display_name: parsed.data.displayName,
    });
    return noStoreJson(data);
  } catch (error) {
    return noStoreJson({ error: safeError(error, "Profil konnte nicht gespeichert werden.") }, { status: 500 });
  }
}
