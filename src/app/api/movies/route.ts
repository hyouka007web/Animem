import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { resolveTaxonomyIds } from "@/lib/pocketbase/taxonomy";
import { getCurrentUser } from "@/lib/auth";
import { can } from "@/lib/permissions";
import { slugify } from "@/lib/slugify";

export async function GET(req: NextRequest) {
  const pb = await createAdminClient();
  const wantsAdmin = new URL(req.url).searchParams.get("admin") === "1";
  if (wantsAdmin) {
    const user = await getCurrentUser();
    if (!user || !can.manageContent(user.role)) return NextResponse.json({ error: "Nicht berechtigt" }, { status: 403 });
  }
  const filter = wantsAdmin ? "" : pb.filter("status = {:status}", { status: "PUBLISHED" });
  const movies = await pb.collection(COL.movies).getFullList({ filter, sort: "-created" });
  return NextResponse.json(movies);
}

export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user || !can.manageContent(user.role)) {
    return NextResponse.json({ error: "Nicht berechtigt" }, { status: 403 });
  }

  const body = await req.json();
  const { title, description, thumbnailUrl, bannerUrl, embedUrl, embedProvider, status, genres, tags } = body;

  if (!title || !thumbnailUrl || !embedUrl) {
    return NextResponse.json(
      { error: "Titel, Thumbnail und Embed-URL sind Pflichtfelder" },
      { status: 400 }
    );
  }

  const pb = await createAdminClient();
  const genreIds = await resolveTaxonomyIds(pb, COL.genres, (genres as string[]) ?? []);
  const tagIds = await resolveTaxonomyIds(pb, COL.tags, (tags as string[]) ?? []);

  try {
    const movie = await pb.collection(COL.movies).create({
      title,
      slug: slugify(title),
      description: description || "",
      thumbnail_url: thumbnailUrl,
      banner_url: bannerUrl || "",
      embed_url: embedUrl,
      embed_provider: embedProvider || "",
      status: status || "DRAFT",
      created_by: user.id,
      genre_ids: genreIds,
      tag_ids: tagIds,
      avg_rating: 0,
      ratings_count: 0,
    });
    return NextResponse.json(movie, { status: 201 });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
