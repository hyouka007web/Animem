// ============================================================
// Legt in einer frischen PocketBase-Instanz automatisch alle
// Collections, Felder, Indizes und API-Regeln an, die Animem
// braucht. Kann gefahrlos mehrfach ausgeführt werden — bereits
// vorhandene Collections werden übersprungen.
//
// Aufruf:  node scripts/pocketbase-setup.mjs
// Voraussetzung: .env.local mit NEXT_PUBLIC_POCKETBASE_URL,
// POCKETBASE_ADMIN_EMAIL, POCKETBASE_ADMIN_PASSWORD.
//
// Hinweis: Das Skript nutzt das "schema"-Format der PocketBase-
// Admin-API (Server-Version ≤ 0.22.x). Bei PocketBase 0.23+ wurde
// das Datenmodell auf "fields" umbenannt — in dem Fall bitte in
// diesem Skript jedes "schema:" zu "fields:" ändern.
// ============================================================

import PocketBase from "pocketbase";
import dotenv from "dotenv";

dotenv.config({ path: ".env.local" });

const url = process.env.NEXT_PUBLIC_POCKETBASE_URL;
const adminEmail = process.env.POCKETBASE_ADMIN_EMAIL;
const adminPassword = process.env.POCKETBASE_ADMIN_PASSWORD;

if (!url || !adminEmail || !adminPassword) {
  console.error(
    "Fehlt: NEXT_PUBLIC_POCKETBASE_URL, POCKETBASE_ADMIN_EMAIL oder POCKETBASE_ADMIN_PASSWORD in .env.local"
  );
  process.exit(1);
}

const pb = new PocketBase(url);

async function ensureCollection(definition) {
  try {
    const existing = await pb.collections.getOne(definition.name);
    const expected = new Set((definition.schema ?? []).map((field) => field.name));
    const actual = new Set((existing.schema ?? []).map((field) => field.name));
    const missing = [...expected].filter((field) => !actual.has(field));
    if (missing.length) {
      throw new Error(`Collection "${definition.name}" exists with incompatible schema. Missing fields: ${missing.join(", ")}. Start with a fresh PocketBase instance instead of mutating legacy data.`);
    }
    console.log(`Collection "${definition.name}" existiert bereits — Schema geprüft.`);
  } catch (error) {
    if (error?.status === 404) {
      await pb.collections.create(definition);
      console.log(`Collection "${definition.name}" angelegt.`);
      return;
    }
    throw error;
  }
}

// Baustein-Helfer, damit die Collection-Definitionen unten übersichtlich bleiben.
const text = (name, opts = {}) => ({ name, type: "text", ...opts });
const num = (name, opts = {}) => ({ name, type: "number", ...opts });
const boolField = (name, opts = {}) => ({ name, type: "bool", ...opts });
const json = (name, opts = {}) => ({ name, type: "json", ...opts });
const select = (name, values, opts = {}) => ({
  name,
  type: "select",
  options: { values, maxSelect: 1 },
  ...opts,
});

async function extendUsersCollection() {
  const existing = await pb.collections.getOne("users");
  const existingFieldNames = new Set(existing.schema.map((f) => f.name));

  const newFields = [
    text("username", { required: true, options: { min: 3, max: 32 } }),
    select("role", ["USER", "ADMIN", "HEAD_ADMIN", "OWNER"], { required: true }),
    text("display_name", { options: { max: 64 } }),
    text("avatar_url", { options: { max: 2000 } }),
    text("bio", { options: { max: 500 } }),
    boolField("is_banned"),
  ].filter((f) => !existingFieldNames.has(f.name));

  if (newFields.length === 0) {
    console.log('Collection "users" hat bereits alle Profilfelder — übersprungen.');
    return;
  }

  await pb.collections.update("users", {
    schema: [...existing.schema, ...newFields],
    indexes: [...(existing.indexes ?? []), "CREATE UNIQUE INDEX idx_username ON users (username)"],
    // The browser must never be allowed to create/update auth records directly.
    // Registration and profile/role changes go through Next.js server APIs.
    createRule: null,
    viewRule: null,
    updateRule: null,
    listRule: null,
    deleteRule: null,
  });
  console.log('Collection "users" um Profilfelder erweitert.');
}

async function main() {
  await pb.admins.authWithPassword(adminEmail, adminPassword);
  console.log("Als Admin eingeloggt.\n");

  await extendUsersCollection();

  // Bilder-Uploads: eine einzige Collection mit Datei-Feld, ersetzt einen
  // klassischen Storage-Bucket. Jeder eingeloggte Nutzer darf hochladen,
  // jeder darf die Bilder sehen (sie werden ja öffentlich angezeigt).
  await ensureCollection({
    name: "uploads",
    type: "base",
    schema: [
      {
        name: "file",
        type: "file",
        required: true,
        options: { maxSelect: 1, maxSize: 10485760, mimeTypes: ["image/png", "image/jpeg", "image/webp", "image/gif"] },
      },
    ],
    listRule: "",
    viewRule: "",
    createRule: "@request.auth.id != ''",
    updateRule: null,
    deleteRule: null,
  });

  // Alle folgenden Collections werden ausschließlich über unsere eigene
  // Next.js-API mit dem Admin-Client angesprochen — die Rechteprüfung
  // (Owner/Head Admin/Admin/User) läuft komplett in lib/permissions.ts.
  // Direkter Zugriff von außen ist daher bewusst gesperrt (null = nur Admin).
  const adminOnly = { listRule: null, viewRule: null, createRule: null, updateRule: null, deleteRule: null };

  await ensureCollection({
    name: "genres",
    type: "base",
    schema: [text("name", { required: true }), text("slug", { required: true })],
    indexes: ["CREATE UNIQUE INDEX idx_genres_slug ON genres (slug)"],
    ...adminOnly,
  });

  await ensureCollection({
    name: "tags",
    type: "base",
    schema: [text("name", { required: true }), text("slug", { required: true })],
    indexes: ["CREATE UNIQUE INDEX idx_tags_slug ON tags (slug)"],
    ...adminOnly,
  });

  await ensureCollection({
    name: "series",
    type: "base",
    schema: [
      text("title", { required: true }),
      text("slug", { required: true }),
      text("description", { options: { max: 5000 } }),
      text("thumbnail_url", { required: true, options: { max: 2000 } }),
      text("banner_url", { options: { max: 2000 } }),
      select("status", ["DRAFT", "PUBLISHED"], { required: true }),
      num("avg_rating"),
      num("ratings_count"),
      num("view_count"),
      text("created_by"),
      json("genre_ids"),
      json("tag_ids"),
    ],
    indexes: ["CREATE UNIQUE INDEX idx_series_slug ON series (slug)"],
    ...adminOnly,
  });

  await ensureCollection({
    name: "seasons",
    type: "base",
    schema: [text("series_id", { required: true }), num("number", { required: true }), text("title")],
    ...adminOnly,
  });

  await ensureCollection({
    name: "episodes",
    type: "base",
    schema: [
      text("season_id", { required: true }),
      num("number", { required: true }),
      text("title", { required: true }),
      text("description", { options: { max: 5000 } }),
      text("embed_url", { required: true, options: { max: 2000 } }),
      text("embed_provider"),
      select("status", ["DRAFT", "PUBLISHED"], { required: true }),
    ],
    ...adminOnly,
  });

  await ensureCollection({
    name: "movies",
    type: "base",
    schema: [
      text("title", { required: true }),
      text("slug", { required: true }),
      text("description", { options: { max: 5000 } }),
      text("thumbnail_url", { required: true, options: { max: 2000 } }),
      text("banner_url", { options: { max: 2000 } }),
      text("embed_url", { required: true, options: { max: 2000 } }),
      text("embed_provider"),
      select("status", ["DRAFT", "PUBLISHED"], { required: true }),
      num("avg_rating"),
      num("ratings_count"),
      text("created_by"),
      json("genre_ids"),
      json("tag_ids"),
    ],
    indexes: ["CREATE UNIQUE INDEX idx_movies_slug ON movies (slug)"],
    ...adminOnly,
  });

  await ensureCollection({
    name: "ratings",
    type: "base",
    schema: [
      text("user_id", { required: true }),
      select("target_type", ["SERIES", "MOVIE", "EPISODE"], { required: true }),
      text("series_id"),
      text("movie_id"),
      text("episode_id"),
      num("value", { required: true, options: { min: 1, max: 10 } }),
    ],
    ...adminOnly,
  });

  await ensureCollection({
    name: "watch_history",
    type: "base",
    schema: [
      text("user_id", { required: true }),
      select("target_type", ["EPISODE", "MOVIE"], { required: true }),
      text("episode_id"),
      text("movie_id"),
      num("progress_sec"),
    ],
    ...adminOnly,
  });

  await ensureCollection({
    name: "watchlist_items",
    type: "base",
    schema: [text("user_id", { required: true }), text("series_id"), text("movie_id")],
    ...adminOnly,
  });

  await ensureCollection({
    name: "subscriptions",
    type: "base",
    schema: [text("user_id", { required: true }), text("series_id", { required: true }), boolField("notify_on_new_episode")],
    ...adminOnly,
  });

  await ensureCollection({
    name: "notifications",
    type: "base",
    schema: [
      text("user_id", { required: true }),
      text("type"),
      text("message", { options: { max: 1000 } }),
      text("link"),
      boolField("is_read"),
    ],
    ...adminOnly,
  });

  await ensureCollection({
    name: "user_collections",
    type: "base",
    schema: [text("user_id", { required: true }), text("title", { required: true }), text("description", { options: { max: 1000 } })],
    ...adminOnly,
  });

  await ensureCollection({
    name: "collection_items",
    type: "base",
    schema: [text("collection_id", { required: true }), text("series_id"), text("movie_id")],
    ...adminOnly,
  });

  await ensureCollection({
    name: "forum_categories",
    type: "base",
    schema: [
      text("name", { required: true }),
      text("slug", { required: true }),
      text("description", { options: { max: 500 } }),
      num("order"),
    ],
    indexes: ["CREATE UNIQUE INDEX idx_forum_categories_slug ON forum_categories (slug)"],
    ...adminOnly,
  });

  await ensureCollection({
    name: "forum_threads",
    type: "base",
    schema: [
      text("category_id", { required: true }),
      text("user_id", { required: true }),
      text("title", { required: true }),
      boolField("is_pinned"),
      boolField("is_locked"),
    ],
    ...adminOnly,
  });

  await ensureCollection({
    name: "forum_posts",
    type: "base",
    schema: [text("thread_id", { required: true }), text("user_id", { required: true }), text("content", { required: true, options: { max: 5000 } })],
    ...adminOnly,
  });

  await ensureCollection({
    name: "tickets",
    type: "base",
    schema: [
      text("user_id", { required: true }),
      text("subject", { required: true }),
      select("priority", ["LOW", "MEDIUM", "HIGH"], { required: true }),
      select("status", ["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"], { required: true }),
    ],
    ...adminOnly,
  });

  await ensureCollection({
    name: "ticket_messages",
    type: "base",
    schema: [
      text("ticket_id", { required: true }),
      text("sender_id", { required: true }),
      text("content", { required: true, options: { max: 5000 } }),
      boolField("is_staff"),
    ],
    ...adminOnly,
  });

  await ensureCollection({
    name: "profile_favorites",
    type: "base",
    schema: [
      text("user_id", { required: true }),
      num("rank", { required: true, options: { min: 1, max: 3 } }),
      text("series_id"),
      text("movie_id"),
    ],
    ...adminOnly,
  });

  console.log("\nFertig! Alle Collections sind angelegt.");
}

main().catch((err) => {
  console.error("\nFehler beim Setup:", err?.response ?? err);
  process.exit(1);
});
