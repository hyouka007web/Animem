import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";

const schema = z.object({
  username: z.string().trim().min(3).max(32).regex(/^[A-Za-z0-9_]+$/),
  email: z.string().trim().email().max(254),
  password: z.string().min(8).max(128),
});

export async function POST(req: NextRequest) {
  try {
    const input = schema.parse(await req.json());
    const pb = await createAdminClient();

    const record = await pb.collection(COL.users).create({
      email: input.email,
      password: input.password,
      passwordConfirm: input.password,
      username: input.username,
      // Never accept a role from the browser. New accounts are always USER.
      role: "USER",
      avatar_url: "",
      bio: "",
      display_name: "",
      is_banned: false,
    });

    const auth = await pb.collection(COL.users).authWithPassword(input.email, input.password);
    return NextResponse.json({
      user: { id: record.id, username: record.username, role: "USER" },
      token: auth.token,
    }, { status: 201 });
  } catch (error: any) {
    if (error instanceof z.ZodError) {
      return NextResponse.json({ error: "Ungültige Registrierungsdaten." }, { status: 400 });
    }
    const status = error?.status === 400 ? 400 : 500;
    return NextResponse.json({ error: "Registrierung fehlgeschlagen." }, { status });
  }
}
