"use client";

import PocketBase from "pocketbase";

export function createBrowserClient(): PocketBase {
  const url = process.env.NEXT_PUBLIC_POCKETBASE_URL;
  if (!url) throw new Error("NEXT_PUBLIC_POCKETBASE_URL is not configured");
  return new PocketBase(url);
}
