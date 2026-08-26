import { NextRequest } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { can } from "@/lib/permissions";
import { enrichWithProfiles } from "@/lib/pocketbase/enrich";
import { ticketMessageSchema } from "@/lib/validation";
import { noStoreJson, rateLimit, rateLimitResponse, safeError } from "@/lib/security";

export async function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  const user = await getCurrentUser();
  if (!user) return noStoreJson({ error: "Nicht angemeldet" }, { status: 401 });
  const pb = await createAdminClient();
  let ticket: any;
  try { ticket = await pb.collection(COL.tickets).getOne(params.id); }
  catch { return noStoreJson({ error: "Ticket nicht gefunden" }, { status: 404 }); }
  if (!can.moderate(user.role) && ticket.user_id !== user.id) return noStoreJson({ error: "Nicht berechtigt" }, { status: 403 });

  const page = Math.max(1, Number(new URL(_req.url).searchParams.get("page") || 1));
  const perPage = Math.min(100, Math.max(1, Number(new URL(_req.url).searchParams.get("limit") || 50)));
  const raw = await pb.collection(COL.ticketMessages).getList(page, perPage, { filter: pb.filter("ticket_id = {:id}", { id: params.id }), sort: "created" });
  const enriched = await enrichWithProfiles(pb, raw.items, "sender_id");
  return noStoreJson(enriched.map(({ user: sender, ...rest }: any) => ({ ...rest, sender })));
}

export async function POST(req: NextRequest, { params }: { params: { id: string } }) {
  const user = await getCurrentUser();
  if (!user) return noStoreJson({ error: "Nicht angemeldet" }, { status: 401 });
  const limit = rateLimit(req, `ticket-message:${user.id}`, 15, 60_000);
  if (!limit.allowed) return rateLimitResponse(limit.retryAfter);
  const parsed = ticketMessageSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return noStoreJson({ error: "Nachricht fehlt oder ist zu lang." }, { status: 400 });

  const isStaff = can.moderate(user.role);
  const pb = await createAdminClient();
  let ticket: any;
  try { ticket = await pb.collection(COL.tickets).getOne(params.id); }
  catch { return noStoreJson({ error: "Ticket nicht gefunden" }, { status: 404 }); }
  if (!isStaff && ticket.user_id !== user.id) return noStoreJson({ error: "Nicht berechtigt" }, { status: 403 });
  if (ticket.status === "CLOSED" && !isStaff) return noStoreJson({ error: "Dieses Ticket ist geschlossen." }, { status: 403 });

  try {
    const data = await pb.collection(COL.ticketMessages).create({ ticket_id: params.id, sender_id: user.id, content: parsed.data.content, is_staff: isStaff });
    if (isStaff) await pb.collection(COL.tickets).update(params.id, { status: "IN_PROGRESS" });
    return noStoreJson(data, { status: 201 });
  } catch (error) {
    return noStoreJson({ error: safeError(error, "Nachricht konnte nicht gesendet werden.") }, { status: 500 });
  }
}
