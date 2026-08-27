import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { SESSION_COOKIE } from "@/lib/pocketbase/server";

export async function DELETE() {
  cookies().delete(SESSION_COOKIE);
  return NextResponse.json({ success: true }, { headers: { "Cache-Control": "no-store" } });
}
