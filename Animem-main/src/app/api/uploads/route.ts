import { NextRequest } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { noStoreJson, rateLimit, rateLimitResponse, safeError } from "@/lib/security";

const MAX_BYTES = 10 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["image/png", "image/jpeg", "image/webp", "image/gif"]);

function matchesSignature(type: string, bytes: Uint8Array) {
  const starts = (values: number[]) => values.every((value, index) => bytes[index] === value);
  if (type === "image/png") return starts([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  if (type === "image/jpeg") return starts([0xff, 0xd8, 0xff]);
  if (type === "image/gif") return starts([0x47, 0x49, 0x46, 0x38]);
  if (type === "image/webp") return starts([0x52, 0x49, 0x46, 0x46]) && bytes[8] === 0x57 && bytes[9] === 0x45 && bytes[10] === 0x42 && bytes[11] === 0x50;
  return false;
}

export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return noStoreJson({ error: "Nicht angemeldet" }, { status: 401 });
  const limit = rateLimit(req, `upload:${user.id}`, 20, 60 * 60_000);
  if (!limit.allowed) return rateLimitResponse(limit.retryAfter);

  const contentLength = Number(req.headers.get("content-length") || 0);
  if (contentLength > MAX_BYTES + 1024 * 1024) return noStoreJson({ error: "Datei ist zu groß." }, { status: 413 });

  let form: FormData;
  try { form = await req.formData(); }
  catch { return noStoreJson({ error: "Ungültiger Upload." }, { status: 400 }); }
  const value = form.get("file");
  if (!(value instanceof File)) return noStoreJson({ error: "Keine Datei übergeben." }, { status: 400 });
  if (value.size === 0 || value.size > MAX_BYTES) return noStoreJson({ error: "Datei muss zwischen 1 Byte und 10 MB groß sein." }, { status: 413 });
  if (!ALLOWED_TYPES.has(value.type)) return noStoreJson({ error: "Nur PNG, JPEG, WebP und GIF sind erlaubt." }, { status: 415 });
  const bytes = new Uint8Array(await value.slice(0, 16).arrayBuffer());
  if (!matchesSignature(value.type, bytes)) return noStoreJson({ error: "Dateiinhalt und Dateityp stimmen nicht überein." }, { status: 415 });

  const pb = await createAdminClient();
  try {
    const record = await pb.collection(COL.uploads).create({ file: value });
    return noStoreJson({ url: pb.files.getUrl(record, record.file), id: record.id }, { status: 201 });
  } catch (error) {
    return noStoreJson({ error: safeError(error, "Upload fehlgeschlagen.") }, { status: 500 });
  }
}
