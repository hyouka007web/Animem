import "server-only";
import type PocketBase from "pocketbase";
import { COL } from "@/lib/pocketbase/collections";

async function fetchByIds(pb: PocketBase, collection: string, ids: string[]) {
  const uniqueIds = [...new Set(ids)];
  const map = new Map<string, any>();
  await Promise.all(
    uniqueIds.map(async (id) => {
      const record = await pb.collection(collection).getOne(id).catch(() => null);
      if (record) map.set(id, record);
    })
  );
  return map;
}

/**
 * Hängt an jeden Record unter `.user` das zugehörige Nutzerprofil an, anhand
 * der Fremdschlüssel-Spalte (z.B. "user_id" oder "sender_id").
 */
export async function enrichWithProfiles<T extends Record<string, any>>(
  pb: PocketBase,
  records: T[],
  foreignKeyField: string
): Promise<(T & { user: any | null })[]> {
  const ids = records.map((record) => record[foreignKeyField]).filter(Boolean);
  const users = await fetchByIds(pb, COL.users, ids);
  return records.map((record) => ({ ...record, user: users.get(record[foreignKeyField]) ?? null }));
}

/**
 * Hängt an jeden Record das referenzierte Ziel an: `.series`, wenn
 * `series_id` gesetzt ist, `.movie`, wenn `movie_id` gesetzt ist.
 */
export async function enrichWithTargets<T extends Record<string, any>>(
  pb: PocketBase,
  records: T[]
): Promise<(T & { series?: any | null; movie?: any | null })[]> {
  const seriesIds = records.map((record) => record.series_id).filter(Boolean);
  const movieIds = records.map((record) => record.movie_id).filter(Boolean);
  const [seriesMap, movieMap] = await Promise.all([
    fetchByIds(pb, COL.series, seriesIds),
    fetchByIds(pb, COL.movies, movieIds),
  ]);
  return records.map((record) => ({
    ...record,
    ...(record.series_id ? { series: seriesMap.get(record.series_id) ?? null } : {}),
    ...(record.movie_id ? { movie: movieMap.get(record.movie_id) ?? null } : {}),
  }));
}
