"use client";

import { useRouter } from "next/navigation";
import { createBrowserClient } from "@/lib/pocketbase/client";

export default function LogoutButton() {
  const router = useRouter();

  async function handleLogout() {
    const pb = createBrowserClient();
    pb.authStore.clear();
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
