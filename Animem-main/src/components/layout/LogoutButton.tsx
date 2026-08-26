"use client";

import { useRouter } from "next/navigation";

export default function LogoutButton() {
  const router = useRouter();

  async function handleLogout() {
    await fetch("/api/auth/session", { method: "DELETE" });
    router.push("/");
    router.refresh();
  }

  return (
    <button onClick={handleLogout} className="hover:text-white">
      Abmelden
    </button>
  );
}
