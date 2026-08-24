import "server-only";
import type PocketBase from "pocketbase";
import { COL } from "@/lib/pocketbase/collections";

type Doc = Record<string, any>;

function pick(doc?: Doc) {
  if (!doc) return null;
  return { id: doc.id, slug: doc.slug, title: doc.title, thumbnail_url: doc.thumbnail_url };
}

// Holt zu einer Liste von Dokumenten mit series_id/movie_id die zugehörigen
// Serien-/Film-Stammdaten (id, slug, title, thumbnail_url).
export async function enrichWithTargets(pb: PocketBase, items: Doc[]) {
  const seriesIds = [...new Set(items.filter((i) => i.series_id).map((i) => i.series_id as string))];
  const movieIds = [...new Set(items.filter((i) => i.movie_id).map((i) => i.movie_id as string))];

  const seriesMap = new Map<string, Doc>();
  const movieMap = new Map<string, Doc>();

  await Promise.all([
    ...seriesIds.map(async (id) => {
      try {
        seriesMap.set(id, await pb.collection(COL.series).getOne(id));
      } catch {
        // Serie wurde gelöscht — Eintrag zeigt dann einfach nichts an
      }
    }),
    ...movieIds.map(async (id) => {
      try {
        movieMap.set(id, await pb.collection(COL.movies).getOne(id));
      } catch {
        // Film wurde gelöscht
      }
    }),
  ]);

  return items.map((item) => ({
    ...item,
    series: item.series_id ? pick(seriesMap.get(item.series_id)) : null,
    movie: item.movie_id ? pick(movieMap.get(item.movie_id)) : null,
  }));
}

// Holt zu einer Liste von Nutzer-IDs die öffentlichen Profildaten (username, avatar_url).
export async function enrichWithProfiles<T extends Doc>(
  pb: PocketBase,
  items: T[],
  idField: string
): Promise<(T & { user: { username: string; avatar_url: string | null } | null })[]> {
  const ids = [...new Set(items.map((i) => i[idField] as string).filter(Boolean))];
  const map = new Map<string, Doc>();

  await Promise.all(
    ids.map(async (id) => {
      try {
        map.set(id, await pb.collection(COL.users).getOne(id));
      } catch {
        // Nutzer existiert nicht mehr
      }
    })
  );

  return items.map((item) => {
    const profile = map.get(item[idField] as string);
    return {
      ...item,
      user: profile ? { username: profile.username, avatar_url: profile.avatar_url ?? null } : null,
    };
  });
}
