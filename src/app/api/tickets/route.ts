import { NextRequest } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { can } from "@/lib/permissions";
import { enrichWithProfiles } from "@/lib/pocketbase/enrich";
import { ticketSchema } from "@/lib/validation";
import { noStoreJson, rateLimit, rateLimitResponse, safeError } from "@/lib/security";

export async function GET(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return noStoreJson({ error: "Nicht angemeldet" }, { status: 401 });
  const page = Math.max(1, Number(req.nextUrl.searchParams.get("page") || 1));
  const perPage = Math.min(50, Math.max(1, Number(req.nextUrl.searchParams.get("limit") || 25)));
  const pb = await createAdminClient();
  const filter = can.moderate(user.role) ? "" : pb.filter("user_id = {:uid}", { uid: user.id });
  const result = await pb.collection(COL.tickets).getList(page, perPage, { filter, sort: "-updated" });
  const withUsers = await enrichWithProfiles(pb, result.items, "user_id");
  const withCounts = await Promise.all(withUsers.map(async (ticket: any) => {
    const messages = await pb.collection(COL.ticketMessages).getList(1, 1, { filter: pb.filter("ticket_id = {:id}", { id: ticket.id }) });
    return { ...ticket, messages: [{ count: messages.totalItems }] };
  }));
  return noStoreJson(withCounts);
}

export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return noStoreJson({ error: "Nicht angemeldet" }, { status: 401 });
  const limit = rateLimit(req, `tickets:${user.id}`, 5, 15 * 60_000);
  if (!limit.allowed) return rateLimitResponse(limit.retryAfter);
  const parsed = ticketSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return noStoreJson({ error: "Ungültige Ticketdaten." }, { status: 400 });

  const pb = await createAdminClient();
  try {
    const ticket = await pb.collection(COL.tickets).create({ user_id: user.id, subject: parsed.data.subject, priority: parsed.data.priority, status: "OPEN" });
    try {
      await pb.collection(COL.ticketMessages).create({ ticket_id: ticket.id, sender_id: user.id, content: parsed.data.message, is_staff: false });
    } catch (error) {
      await pb.collection(COL.tickets).delete(ticket.id).catch(() => undefined);
      throw error;
    }
    return noStoreJson(ticket, { status: 201 });
  } catch (error) {
    return noStoreJson({ error: safeError(error, "Ticket konnte nicht erstellt werden.") }, { status: 500 });
  }
}
