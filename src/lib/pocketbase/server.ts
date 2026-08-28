import "server-only";
import PocketBase from "pocketbase";
import { COL } from "@/lib/pocketbase/collections";

export const SESSION_COOKIE = "animem_session";

const POCKETBASE_URL = process.env.NEXT_PUBLIC_POCKETBASE_URL;

if (!POCKETBASE_URL) {
  throw new Error("NEXT_PUBLIC_POCKETBASE_URL ist nicht gesetzt.");
}

let adminClientPromise: Promise<PocketBase> | null = null;

async function authenticateAdmin(): Promise<PocketBase> {
  const adminEmail = process.env.POCKETBASE_ADMIN_EMAIL;
  const adminPassword = process.env.POCKETBASE_ADMIN_PASSWORD;
  if (!adminEmail || !adminPassword) {
    throw new Error("POCKETBASE_ADMIN_EMAIL oder POCKETBASE_ADMIN_PASSWORD ist nicht gesetzt.");
  }
  const pb = new PocketBase(POCKETBASE_URL);
  await pb.admins.authWithPassword(adminEmail, adminPassword);
  return pb;
}

/**
 * Liefert einen als Admin authentifizierten PocketBase-Client. Die
 * Admin-Session wird pro Serverprozess wiederverwendet und bei Bedarf
 * erneuert, statt bei jedem Aufruf neu zu authentifizieren.
 */
export async function createAdminClient(): Promise<PocketBase> {
  if (!adminClientPromise) {
    adminClientPromise = authenticateAdmin();
  }

  try {
    const pb = await adminClientPromise;
    if (!pb.authStore.isValid) {
      adminClientPromise = authenticateAdmin();
      return await adminClientPromise;
    }
    return pb;
  } catch (error) {
    adminClientPromise = null;
    throw error;
  }
}

/**
 * Authentifiziert einen Nutzer per E-Mail/Passwort gegen die "users"-Auth-
 * Collection und gibt Token + Nutzerdatensatz zurück.
 */
export async function authenticateUser(email: string, password: string) {
  const pb = new PocketBase(POCKETBASE_URL);
  const auth = await pb.collection(COL.users).authWithPassword(email, password);
  return { token: auth.token, record: auth.record };
}

/**
 * Prüft ein Session-Token (aus dem Cookie) gegen PocketBase und liefert bei
 * Gültigkeit den aktuellen Nutzerdatensatz zurück, sonst null.
 */
export async function getUserFromToken(token: string) {
  const pb = new PocketBase(POCKETBASE_URL);
  pb.authStore.save(token, null);
  try {
    const auth = await pb.collection(COL.users).authRefresh();
    return auth.record;
  } catch {
    return null;
  }
}
