import "server-only";
import { cookies } from "next/headers";
import { SESSION_COOKIE, getUserFromToken } from "@/lib/pocketbase/server";
import type { Role } from "@/lib/permissions";

export interface CurrentUser {
  id: string;
  username: string;
  role: Role;
  avatarUrl: string | null;
}

// Server-seitiger Helfer: liefert den eingeloggten Nutzer inkl. Rolle, oder
// null wenn nicht eingeloggt. Bei PocketBase ist der Auth-Datensatz zugleich
// das Profil — keine separate Profil-Tabelle nötig.
export async function getCurrentUser(): Promise<CurrentUser | null> {
  const token = cookies().get(SESSION_COOKIE)?.value;
  if (!token) return null;

  const record = await getUserFromToken(token);
  if (!record) return null;

  return {
    id: record.id,
    username: record.username,
    role: record.role as Role,
    avatarUrl: record.avatar_url || null,
  };
}
