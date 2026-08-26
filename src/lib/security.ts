import "server-only";
import { NextRequest, NextResponse } from "next/server";

interface Bucket { count: number; resetAt: number }

const buckets = new Map<string, Bucket>();

function now() { return Date.now(); }

function clientIp(req: NextRequest): string {
  const forwarded = req.headers.get("x-forwarded-for");
  if (forwarded) return forwarded.split(",")[0].trim().slice(0, 100) || "unknown";
  return req.headers.get("x-real-ip")?.slice(0, 100) || "unknown";
}

/** Lightweight per-process rate limiting. It is deliberately fail-open on storage errors and
 * should be paired with a platform/WAF limit for multi-instance deployments. */
export function rateLimit(req: NextRequest, scope: string, limit: number, windowMs: number) {
  const key = `${scope}:${clientIp(req)}`;
  const timestamp = now();
  const current = buckets.get(key);

  if (buckets.size > 10_000) {
    for (const [bucketKey, bucket] of buckets) {
      if (bucket.resetAt <= timestamp) buckets.delete(bucketKey);
    }
  }

  if (!current || current.resetAt <= timestamp) {
    buckets.set(key, { count: 1, resetAt: timestamp + windowMs });
    return { allowed: true, retryAfter: 0 };
  }

  current.count += 1;
  if (current.count <= limit) return { allowed: true, retryAfter: 0 };

  return { allowed: false, retryAfter: Math.max(1, Math.ceil((current.resetAt - timestamp) / 1000)) };
}

export function rateLimitResponse(retryAfter: number) {
  return NextResponse.json(
    { error: "Zu viele Anfragen. Bitte kurz warten und erneut versuchen." },
    { status: 429, headers: { "Retry-After": String(retryAfter), "Cache-Control": "no-store" } }
  );
}

export function noStoreJson(data: unknown, init?: ResponseInit) {
  const headers = new Headers(init?.headers);
  headers.set("Cache-Control", "no-store");
  return NextResponse.json(data, { ...init, headers });
}

export function safeError(error: unknown, fallback = "Die Anfrage konnte nicht verarbeitet werden.") {
  if (process.env.NODE_ENV !== "production" && error instanceof Error) return error.message;
  return fallback;
}

