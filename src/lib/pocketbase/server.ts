import "server-only";
import PocketBase from "pocketbase";

export const SESSION_COOKIE = "animem-session";

function requiredEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
}

export const PB_URL = requiredEnv("NEXT_PUBLIC_POCKETBASE_URL");

let cachedAdmin: PocketBase | null = null;

export async function createAdminClient(): Promise<PocketBase> {
  if (cachedAdmin && cachedAdmin.authStore.isValid) return cachedAdmin;

  const pb = new PocketBase(PB_URL);
  pb.autoCancellation(false);
  await pb.admins.authWithPassword(
    requiredEnv("POCKETBASE_ADMIN_EMAIL"),
    requiredEnv("POCKETBASE_ADMIN_PASSWORD")
  );

  cachedAdmin = pb;
  return pb;
}

export async function getUserFromToken(token: string) {
  const pb = new PocketBase(PB_URL);
  pb.authStore.save(token, null);

  try {
    const result = await pb.collection("users").authRefresh();
    return result.record;
  } catch {
    return null;
  }
}
