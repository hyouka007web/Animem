import { redirect } from "next/navigation";
import { createAdminClient } from "@/lib/pocketbase/server";
import { COL } from "@/lib/pocketbase/collections";
import { getCurrentUser } from "@/lib/auth";
import { can } from "@/lib/permissions";
import UserRoleTable from "@/components/admin/UserRoleTable";

export default async function AdminUsersPage() {
  const user = await getCurrentUser();
  if (!user || !can.manageAdmins(user.role)) redirect("/admin");

  const pb = await createAdminClient();
  const raw = await pb.collection(COL.users).getFullList({ sort: "-created" });

  const users = raw.map((u) => ({
    id: u.id,
    username: u.username,
    role: u.role,
    is_banned: u.is_banned,
    created_at: u.created,
  }));

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Admins & Nutzer</h1>
      <UserRoleTable initialUsers={users} actorId={user.id} actorRole={user.role} />
    </div>
  );
}
