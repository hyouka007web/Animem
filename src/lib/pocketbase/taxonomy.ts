import "server-only";
import type PocketBase from "pocketbase";
import { COL } from "@/lib/pocketbase/collections";
import { slugify } from "@/lib/slugify";

// PocketBase kennt kein "upsert by unique column". Wir suchen daher zuerst
// per Slug und legen nur an, wenn wirklich noch nichts existiert. Wird von
// Serien- und Film-Erstellung/Bearbeitung gleichermaßen genutzt.
export async function resolveTaxonomyIds(
  pb: PocketBase,
  collection: typeof COL.genres | typeof COL.tags,
  names: string[]
): Promise<string[]> {
  const ids: string[] = [];

  for (const rawName of names) {
    const name = rawName.trim();
    if (!name) continue;
    const slug = slugify(name);

    try {
      const existing = await pb.collection(collection).getFirstListItem(pb.filter("slug = {:slug}", { slug }));
      ids.push(existing.id);
      continue;
    } catch {
      // Noch nicht vorhanden — unten neu anlegen
    }

    const created = await pb.collection(collection).create({ name, slug });
    ids.push(created.id);
  }

  return ids;
}

// Für die Admin-Tabellen: löst genre_ids/tag_ids zurück zu Namen auf, im
// Format, das SeriesFormModal/SeriesTable erwarten ([{ genre: { name } }]).
export async function loadTaxonomyNames(
  pb: PocketBase,
  collection: typeof COL.genres | typeof COL.tags,
  ids: string[],
  wrapperKey: "genre" | "tag"
) {
  const results = await Promise.all(
    ids.map(async (id) => {
      try {
        const doc = await pb.collection(collection).getOne(id);
        return { [wrapperKey]: { name: doc.name } };
      } catch {
        return null;
      }
    })
  );
  return results.filter(Boolean);
}

// Für Kategorie-/Tag-Detailseiten: lädt alle veröffentlichten Serien/Filme,
// deren genre_ids bzw. tag_ids das gesuchte Genre/Tag enthalten. genre_ids/
// tag_ids liegen als JSON-Array von IDs vor — "~" prüft eine Teilstring-
// Übereinstimmung in der serialisierten Form, was für feste ID-Strings
// zuverlässig funktioniert.
export async function findByTaxonomy(
  pb: PocketBase,
  collection: typeof COL.series | typeof COL.movies,
  field: "genre_ids" | "tag_ids",
  taxonomyId: string
) {
  const filter = pb.filter(`${field} ~ {:id} && status = "PUBLISHED"`, { id: taxonomyId });
  return await pb.collection(collection).getFullList({ filter });
}
