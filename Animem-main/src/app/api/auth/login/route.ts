import { NextRequest } from "next/server";
import { z } from "zod";
import { authenticateUser, SESSION_COOKIE } from "@/lib/pocketbase/server";
import { noStoreJson, rateLimit, rateLimitResponse } from "@/lib/security";
import { cookies } from "next/headers";

const schema = z.object({ email: z.string().trim().email().max(254), password: z.string().min(1).max(128) });

export async function POST(req: NextRequest) {
  const limit = rateLimit(req, "auth-login", 8, 15 * 60_000);
  if (!limit.allowed) return rateLimitResponse(limit.retryAfter);

  const parsed = schema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return noStoreJson({ error: "E-Mail oder Passwort ist falsch." }, { status: 401 });

  try {
    const auth = await authenticateUser(parsed.data.email, parsed.data.password);
    if (auth.record?.is_banned === true) return noStoreJson({ error: "E-Mail oder Passwort ist falsch." }, { status: 401 });
    cookies().set(SESSION_COOKIE, auth.token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 14,
    });
    return noStoreJson({ user: { id: auth.record.id, username: auth.record.username, role: auth.record.role } });
  } catch {
    return noStoreJson({ error: "E-Mail oder Passwort ist falsch." }, { status: 401 });
  }
}
