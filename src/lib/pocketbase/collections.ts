// ============================================================
// Zentrale Liste aller PocketBase-Collection-Namen.
// Immer von hier importieren statt Strings zu wiederholen —
// so bleibt ein Tippfehler an einer Stelle statt an zwanzig.
//
// "users" ist PocketBase's eingebaute Auth-Collection — bei uns
// zugleich das Profil (username, role, avatar_url, bio, …ist alles
// direkt am Nutzer-Datensatz, keine separate Profil-Tabelle nötig).
// ============================================================

export const COL = {
  users: "users",
  uploads: "uploads",
  genres: "genres",
  tags: "tags",
  series: "series",
  seasons: "seasons",
  episodes: "episodes",
  movies: "movies",
  ratings: "ratings",
  watchHistory: "watch_history",
  watchlistItems: "watchlist_items",
  subscriptions: "subscriptions",
  notifications: "notifications",
  userCollections: "user_collections",
  collectionItems: "collection_items",
  forumCategories: "forum_categories",
  forumThreads: "forum_threads",
  forumPosts: "forum_posts",
  tickets: "tickets",
  ticketMessages: "ticket_messages",
  profileFavorites: "profile_favorites",
} as const;
