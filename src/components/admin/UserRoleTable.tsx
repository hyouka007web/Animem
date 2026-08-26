"use client";

import { useState } from "react";
import { assignableRoles, canManageTargetRole, type Role } from "@/lib/permissions";

interface UserRow {
  id: string;
  username: string;
  role: Role;
  is_banned: boolean;
}

const ROLE_LABELS: Record<Role, string> = {
  OWNER: "Owner",
  HEAD_ADMIN: "Head Admin",
  ADMIN: "Admin",
  USER: "User",
};

export default function UserRoleTable({
  initialUsers,
  actorId,
  actorRole,
}: {
  initialUsers: UserRow[];
  actorId: string;
  actorRole: Role;
}) {
  const [users, setUsers] = useState(initialUsers);
  const [error, setError] = useState<string | null>(null);

  async function changeRole(id: string, role: string) {
    setError(null);
    const res = await fetch(`/api/users/${id}/role`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
    if (res.ok) {
      const updated = await res.json();
      setUsers((prev) => prev.map((u) => (u.id === id ? { ...u, role: updated.role } : u)));
    } else {
      const body = await res.json().catch(() => null);
      setError(body?.error || "Rolle konnte nicht geändert werden.");
    }
  }

  const options = assignableRoles(actorRole);

  return (
    <div>
      {error && (
        <p className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-300">
          {error}
        </p>
      )}
      <div className="overflow-hidden rounded-xl border border-white/10">
        <table className="w-full text-left text-sm">
          <thead className="bg-white/5 text-neutral-400">
            <tr>
              <th className="px-4 py-3 font-medium">Nutzer</th>
              <th className="px-4 py-3 font-medium">Rolle</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {users.map((u) => {
              const isSelf = u.id === actorId;
              const canEdit = !isSelf && options.length > 0 && canManageTargetRole(actorRole, u.role);

              return (
                <tr key={u.id} className="hover:bg-white/[0.03]">
                  <td className="px-4 py-3">
                    {u.username}
                    {isSelf && <span className="ml-2 text-xs text-neutral-500">(du)</span>}
                  </td>
                  <td className="px-4 py-3">
                    {canEdit ? (
                      <select
                        value={u.role}
                        onChange={(e) => changeRole(u.id, e.target.value)}
                        className="rounded-lg border border-white/10 bg-neutral-800 px-2 py-1 text-sm"
                      >
                        {/* aktuelle Rolle immer mit anzeigen, auch falls sie außerhalb der eigenen Vergabe-Optionen liegt */}
                        {!options.includes(u.role) && <option value={u.role}>{ROLE_LABELS[u.role]}</option>}
                        {options.map((r) => (
                          <option key={r} value={r}>
                            {ROLE_LABELS[r]}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className="text-neutral-400">{ROLE_LABELS[u.role]}</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
