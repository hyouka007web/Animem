import { z } from "zod";

const httpUrl = z.string().trim().url().max(2000).refine((value) => {
  try { return ["https:"].includes(new URL(value).protocol); } catch { return false; }
}, "Nur HTTPS-URLs sind erlaubt.");

export const registrationSchema = z.object({
  username: z.string().trim().min(3).max(32).regex(/^[A-Za-z0-9_]+$/),
  email: z.string().trim().email().max(254),
  password: z.string().min(8).max(128),
});


export const forumPostSchema = z.object({
  threadId: z.string().trim().min(1).max(64),
  content: z.string().trim().min(1).max(5000),
});

export const forumThreadSchema = z.object({
  categoryId: z.string().trim().min(1).max(64),
  title: z.string().trim().min(3).max(160),
  content: z.string().trim().min(1).max(5000),
});

export const ratingSchema = z.object({
  targetType: z.enum(["SERIES", "MOVIE", "EPISODE"]),
  seriesId: z.string().trim().min(1).max(64).optional(),
  movieId: z.string().trim().min(1).max(64).optional(),
  episodeId: z.string().trim().min(1).max(64).optional(),
  value: z.coerce.number().int().min(1).max(10),
}).superRefine((data, ctx) => {
  const expected = data.targetType === "SERIES" ? data.seriesId : data.targetType === "MOVIE" ? data.movieId : data.episodeId;
  const others = [data.seriesId, data.movieId, data.episodeId].filter(Boolean);
  if (!expected || others.length !== 1) ctx.addIssue({ code: "custom", path: ["targetType"], message: "Genau eine passende Ziel-ID ist erforderlich." });
});

export const watchlistSchema = z.object({
  seriesId: z.string().trim().min(1).max(64).optional(),
  movieId: z.string().trim().min(1).max(64).optional(),
}).refine((data) => Boolean(data.seriesId) !== Boolean(data.movieId), "Genau eine Ziel-ID ist erforderlich.");

export const subscriptionSchema = z.object({ seriesId: z.string().trim().min(1).max(64) });

export const profileSchema = z.object({
  avatarUrl: z.string().trim().max(2000).refine((v) => !v || httpUrl.safeParse(v).success, "Avatar muss eine HTTPS-URL sein."),
  bio: z.string().trim().max(500),
  displayName: z.string().trim().max(64),
});

export const favoriteSchema = z.object({
  rank: z.coerce.number().int().min(1).max(3),
  seriesId: z.string().trim().min(1).max(64).optional(),
  movieId: z.string().trim().min(1).max(64).optional(),
}).refine((data) => Boolean(data.seriesId) !== Boolean(data.movieId), "Genau eine Ziel-ID ist erforderlich.");

export const ticketSchema = z.object({
  subject: z.string().trim().min(3).max(160),
  message: z.string().trim().min(1).max(5000),
  priority: z.enum(["LOW", "MEDIUM", "HIGH"]).default("MEDIUM"),
});

export const ticketMessageSchema = z.object({ content: z.string().trim().min(1).max(5000) });

export const roleSchema = z.object({ role: z.enum(["USER", "ADMIN", "HEAD_ADMIN", "OWNER"]) });

const episodeSchema = z.object({
  id: z.string().trim().min(1).max(64).optional(),
  number: z.coerce.number().int().min(1).max(10000),
  title: z.string().trim().min(1).max(200),
  embedUrl: httpUrl,
  embedProvider: z.string().trim().max(100).optional().default(""),
});

const seasonSchema = z.object({
  id: z.string().trim().min(1).max(64).optional(),
  number: z.coerce.number().int().min(1).max(1000),
  title: z.string().trim().max(200).optional().default(""),
  episodes: z.array(episodeSchema).max(500).default([]),
});

export const seriesSchema = z.object({
  title: z.string().trim().min(1).max(200),
  description: z.string().trim().max(5000).default(""),
  thumbnailUrl: httpUrl,
  bannerUrl: z.string().trim().max(2000).refine((v) => !v || httpUrl.safeParse(v).success, "Banner muss eine HTTPS-URL sein."),
  status: z.enum(["DRAFT", "PUBLISHED", "ARCHIVED"]).default("DRAFT"),
  genres: z.array(z.string().trim().min(1).max(80)).max(50).default([]),
  tags: z.array(z.string().trim().min(1).max(80)).max(100).default([]),
  seasons: z.array(seasonSchema).max(50).default([]),
});

export const movieSchema = z.object({
  title: z.string().trim().min(1).max(200),
  description: z.string().trim().max(5000).default(""),
  thumbnailUrl: httpUrl,
  bannerUrl: z.string().trim().max(2000).refine((v) => !v || httpUrl.safeParse(v).success, "Banner muss eine HTTPS-URL sein."),
  embedUrl: httpUrl,
  embedProvider: z.string().trim().max(100).default(""),
  status: z.enum(["DRAFT", "PUBLISHED"]).default("DRAFT"),
  genres: z.array(z.string().trim().min(1).max(80)).max(50).default([]),
  tags: z.array(z.string().trim().min(1).max(80)).max(100).default([]),
});

export const movieUpdateSchema = movieSchema.partial().extend({
  title: movieSchema.shape.title.optional(),
});
