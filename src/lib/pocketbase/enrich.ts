import "server-only";
import type PocketBase from "pocketbase";
import { COL } from "@/lib/pocketbase/collections";

type Doc = Record<string, any>;

function pick(doc?: Doc) {
  if (!doc) return null;
  return { id: doc.id, slug: doc.slug, title: doc.title, thumbnail_url: doc.thumbnail_url };
}

function orIdFilter(pb: PocketBase, ids: string[]) {
  return ids.map((_, index) => `id = {:id${index}}`).join(" || ");
}

async function getByIds(pb: PocketBase, collection: string, ids: string[]) {
  if (!ids.length) return new Map<string, Doc>();
  const unique = [...new Set(ids)].slice(0, 200);
  const params = Object.fromEntries(unique.map((id, index) => [`id${index}`, id]));
  const filter = pb.filter(orIdFilter(pb, unique), params);
  const records = await pb.collection(collection).getFullList({ filter });
  return new Map(records.map((record) => [record.id, record]));
}

export async function enrichWithTargets(pb: PocketBase, items: Doc[]) {
  const seriesIds = items.filter((i) => i.series_id).map((i) => i.series_id as string);
  const movieIds = items.filter((i) => i.movie_id).map((i) => i.movie_id as string);
  const [seriesMap, movieMap] = await Promise.all([
    getByIds(pb, COL.series, seriesIds),
    getByIds(pb, COL.movies, movieIds),
  ]);

  return items.map((item) => ({
    ...item,
    series: item.series_id ? pick(seriesMap.get(item.series_id)) : null,
    movie: item.movie_id ? pick(movieMap.get(item.movie_id)) : null,
  }));
}

export async function enrichWithProfiles<T extends Doc>(
  pb: PocketBase,
  items: T[],
  idField: string,
): Promise<(T & { user: { username: string; avatar_url: string | null } | null })[]> {
  const ids = items.map((i) => i[idField] as string).filter(Boolean);
  const map = await getByIds(pb, COL.users, ids);
  return items.map((item) => {
    const profile = map.get(item[idField] as string);
    return {
      ...item,
      user: profile ? { username: profile.username, avatar_url: profile.avatar_url ?? null } : null,
    };
  });
}
