import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { SESSION_COOKIE, getUserFromToken } from "@/lib/pocketbase/server";

// Speichert den PocketBase-Auth-Token (vom Browser-Login/Registrierung) als
// sicheres, httpOnly-Cookie, damit der Server bei jedem Request weiß, wer da ist.
export async function POST(req: NextRequest) {
  const { token } = await req.json();
  if (!token || typeof token !== "string") return NextResponse.json({ error: "Kein gültiges Token übergeben" }, { status: 400 });

  const user = await getUserFromToken(token);
  if (!user) return NextResponse.json({ error: "Ungültige Sitzung" }, { status: 401 });

  cookies().set(SESSION_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 14, // 14 Tage — entspricht PocketBase's Standard-Token-Laufzeit
  });

  return NextResponse.json({ success: true }, { headers: { "Cache-Control": "no-store" } });
}

export async function DELETE() {
  cookies().delete(SESSION_COOKIE);
  return NextResponse.json({ success: true }, { headers: { "Cache-Control": "no-store" } });
}
