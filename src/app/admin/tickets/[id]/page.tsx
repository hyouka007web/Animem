import { notFound } from "next/navigation";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import TicketChat from "@/components/tickets/TicketChat";

export default async function AdminTicketDetailPage({ params }: { params: { id: string } }) {
  const pb = await createAdminClient();

  let ticket;
  try {
    ticket = await pb.collection(COL.tickets).getOne(params.id);
  } catch {
    notFound();
  }

  let user: any = null;
  try {
    user = await pb.collection(COL.users).getOne(ticket!.user_id);
  } catch {}

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
    <div>
      <h1 className="mb-1 text-xl font-bold">{ticket!.subject}</h1>
      <p className="mb-6 text-sm text-neutral-400">von {user?.username}</p>
      <TicketChat ticketId={ticket!.id} messages={messages as any} />
    </div>
  );
}
