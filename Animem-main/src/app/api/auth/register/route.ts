import { NextRequest } from "next/server";
import { ZodError } from "zod";
import { authenticateUser, createAdminClient, SESSION_COOKIE } from "@/lib/pocketbase/server";
import { cookies } from "next/headers";
import { COL } from "@/lib/pocketbase/collections";
import { registrationSchema } from "@/lib/validation";
import { noStoreJson, rateLimit, rateLimitResponse } from "@/lib/security";

export async function POST(req: NextRequest) {
  const limit = rateLimit(req, "auth-register", 5, 15 * 60_000);
  if (!limit.allowed) return rateLimitResponse(limit.retryAfter);

  try {
    const input = registrationSchema.parse(await req.json());
    const pb = await createAdminClient();

    const record = await pb.collection(COL.users).create({
      email: input.email,
      password: input.password,
      passwordConfirm: input.password,
      username: input.username,
      role: "USER",
      avatar_url: "",
      bio: "",
      display_name: "",
      is_banned: false,
    });

    const auth = await authenticateUser(input.email, input.password);
    cookies().set(SESSION_COOKIE, auth.token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 14,
    });
    return noStoreJson({ user: { id: record.id, username: record.username, role: "USER" } }, { status: 201 });
  } catch (error: unknown) {
    if (error instanceof ZodError) return noStoreJson({ error: "Ungültige Registrierungsdaten." }, { status: 400 });
    const status = (error as { status?: number })?.status === 400 ? 400 : 500;
    return noStoreJson({ error: status === 400 ? "E-Mail oder Benutzername wird bereits verwendet." : "Registrierung fehlgeschlagen." }, { status });
  }
}
