import { NextRequest, NextResponse } from "next/server";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { can } from "@/lib/permissions";
import { enrichWithProfiles } from "@/lib/pocketbase/enrich";

// User sieht nur eigene Tickets, Staff (Admin+) sieht alle — die Prüfung
// passiert hier im Code (statt per API-Regeln direkt in PocketBase).
export async function GET() {
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "Nicht angemeldet" }, { status: 401 });

  const pb = await createAdminClient();
  const filter = can.moderate(user.role) ? "" : pb.filter("user_id = {:uid}", { uid: user.id });

  const raw = await pb.collection(COL.tickets).getFullList({ filter, sort: "-updated" });
  const withUsers = await enrichWithProfiles(pb, raw, "user_id");

  const withCounts = await Promise.all(
    withUsers.map(async (ticket: any) => {
      const messages = await pb.collection(COL.ticketMessages).getList(1, 1, {
        filter: pb.filter("ticket_id = {:id}", { id: ticket.id }),
      });
      return { ...ticket, messages: [{ count: messages.totalItems }] };
    })
  );

  return NextResponse.json(withCounts);
}

export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "Nicht angemeldet" }, { status: 401 });

  const { subject, message, priority } = await req.json();
  if (!subject || !message) {
    return NextResponse.json({ error: "Betreff und Nachricht sind Pflichtfelder" }, { status: 400 });
  }

  const pb = await createAdminClient();

  let ticket;
  try {
    ticket = await pb.collection(COL.tickets).create({
      user_id: user.id,
      subject,
      priority: priority || "MEDIUM",
      status: "OPEN",
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }

  await pb.collection(COL.ticketMessages).create({
    ticket_id: ticket.id,
    sender_id: user.id,
    content: message,
    is_staff: false,
  });

  return NextResponse.json(ticket, { status: 201 });
}
