import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/auth";
import { can, type Role } from "@/lib/permissions";
import AdminShell, { type AdminIconKey } from "@/components/admin/AdminShell";

const NAV_ITEMS: {
  href: string;
  label: string;
  icon: AdminIconKey;
  minRole: Role;
}[] = [
  { href: "/admin", label: "Übersicht", icon: "dashboard", minRole: "ADMIN" },
  { href: "/admin/series", label: "Serien", icon: "series", minRole: "ADMIN" },
  { href: "/admin/movies", label: "Filme", icon: "movies", minRole: "ADMIN" },
  { href: "/admin/forum", label: "Forum", icon: "forum", minRole: "ADMIN" },
  { href: "/admin/tickets", label: "Support-Tickets", icon: "tickets", minRole: "ADMIN" },
  { href: "/admin/users", label: "Admins & Nutzer", icon: "users", minRole: "HEAD_ADMIN" },
  { href: "/admin/settings", label: "Einstellungen", icon: "settings", minRole: "OWNER" },
];

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const user = await getCurrentUser();

  if (!user || !can.manageContent(user.role)) {
    redirect("/");
  }

  const visibleItems = NAV_ITEMS.filter((item) => {
    if (item.minRole === "OWNER") return user.role === "OWNER";
    if (item.minRole === "HEAD_ADMIN") return can.manageAdmins(user.role);
    return can.manageContent(user.role);
  }).map(({ href, label, icon }) => ({ href, label, icon }));

  return (
    <AdminShell navItems={visibleItems} username={user.username} role={user.role}>
      {children}
    </AdminShell>
  );
}
