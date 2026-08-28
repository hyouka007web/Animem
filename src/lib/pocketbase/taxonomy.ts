import "server-only";
import type PocketBase from "pocketbase";
import { slugify, uniqueSlug } from "@/lib/slugify";

/**
 * Nimmt eine Liste von Namen (z.B. Genre- oder Tag-Bezeichnungen, wie sie im
 * Formular eingegeben werden) und liefert die passenden Record-IDs zurück.
 * Bereits vorhandene Einträge (Vergleich case-insensitive über den Slug)
 * werden wiederverwendet, fehlende neu angelegt.
 */
export async function resolveTaxonomyIds(pb: PocketBase, collection: string, names: string[]): Promise<string[]> {
  const ids: string[] = [];
  for (const rawName of names) {
    const name = rawName.trim();
    if (!name) continue;
    const slug = slugify(name);
    const existing = await pb.collection(collection).getFirstListItem(pb.filter("slug = {:slug}", { slug })).catch(() => null);
    if (existing) {
      ids.push(existing.id);
      continue;
    }
    const created = await pb.collection(collection).create({ name, slug: await uniqueSlug(pb, collection, name) });
    ids.push(created.id);
  }
  return ids;
}

/**
 * Kehrt resolveTaxonomyIds um: lädt zu einer Liste von IDs die Namen. IDs, zu
 * denen kein Datensatz (mehr) existiert, werden stillschweigend übersprungen.
 */
export async function loadTaxonomyNames(pb: PocketBase, collection: string, ids: string[], _kind: "genre" | "tag"): Promise<string[]> {
  const names = await Promise.all(
    ids.map((id) => pb.collection(collection).getOne(id).then((record) => record.name as string).catch(() => null))
  );
  return names.filter((name): name is string => Boolean(name));
}

/**
 * Findet alle Datensätze einer Collection, deren JSON-Array-Feld (z.B.
 * genre_ids/tag_ids) die angegebene Taxonomie-ID enthält.
 */
export async function findByTaxonomy(pb: PocketBase, collection: string, field: string, taxonomyId: string) {
  return pb.collection(collection).getFullList({
    filter: pb.filter(`${field} ~ {:id}`, { id: taxonomyId }),
    sort: "-avg_rating",
  });
}
