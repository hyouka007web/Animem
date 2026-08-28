import "server-only";
import type PocketBase from "pocketbase";

export function slugify(input: string): string {
  return input
    .toLowerCase()
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .replace(/[^\p{L}\p{N}\s-]/gu, "")
    .trim()
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-");
}

export async function uniqueSlug(pb: PocketBase, collection: string, title: string, currentId?: string) {
  const base = slugify(title) || "item";
  let candidate = base;
  for (let i = 1; i <= 100; i += 1) {
    const existing = await pb.collection(collection).getFirstListItem(pb.filter("slug = {:slug}", { slug: candidate })).catch(() => null);
    if (!existing || existing.id === currentId) return candidate;
    candidate = `${base}-${i + 1}`;
  }
  throw new Error("Kein eindeutiger Slug konnte erzeugt werden.");
}
