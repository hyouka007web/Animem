import { notFound } from "next/navigation";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { can } from "@/lib/permissions";
import TicketChat from "@/components/tickets/TicketChat";

export default async function TicketDetailPage({ params }: { params: { id: string } }) {
  const user = await getCurrentUser();
  if (!user) notFound();

  const pb = await createAdminClient();

  let ticket;
  try {
    ticket = await pb.collection(COL.tickets).getOne(params.id);
  } catch {
    notFound();
  }

  // Eigentümer oder Staff (Admin+) darf das Ticket sehen
  if (ticket!.user_id !== user.id && !can.moderate(user.role)) notFound();

  const messagesRaw = await pb.collection(COL.ticketMessages).getFullList({
    filter: pb.filter("ticket_id = {:id}", { id: params.id }),
    sort: "created",
  });

  const messages = await Promise.all(
    messagesRaw.map(async (m) => {
      let sender: any = null;
      try {
        sender = await pb.collection(COL.users).getOne(m.sender_id);
      } catch {}
      return { id: m.id, content: m.content, is_staff: m.is_staff, created_at: m.created, sender: sender ? { username: sender.username } : null };
    })
  );

  return (
    <div className="min-h-screen bg-neutral-950 px-4 py-8 text-white">
      <div className="mx-auto max-w-2xl">
        <h1 className="mb-6 text-xl font-bold">{ticket!.subject}</h1>
        <TicketChat ticketId={ticket!.id} messages={messages as any} />
      </div>
    </div>
  );
}
