import "server-only";
import PocketBase from "pocketbase";

export const SESSION_COOKIE = "animem-session";

function requiredEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
}

const rawPbUrl = requiredEnv("NEXT_PUBLIC_POCKETBASE_URL");
let parsedPbUrl: URL;
try { parsedPbUrl = new URL(rawPbUrl); } catch { throw new Error("NEXT_PUBLIC_POCKETBASE_URL muss eine gültige URL sein."); }
if (process.env.NODE_ENV === "production" && parsedPbUrl.protocol !== "https:") {
  throw new Error("NEXT_PUBLIC_POCKETBASE_URL muss in Produktion HTTPS verwenden.");
}
export const PB_URL = parsedPbUrl.toString().replace(/\/$/, "");

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

export async function authenticateUser(email: string, password: string) {
  const pb = new PocketBase(PB_URL);
  pb.autoCancellation(false);
  const auth = await pb.collection("users").authWithPassword(email, password);
  return { token: auth.token, record: auth.record };
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
