"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { AtSign, User as UserIcon } from "lucide-react";

interface Props {
  username: string;
  showAt?: boolean; // "@username" statt "username" anzeigen
  className?: string;
}

// Zeigt einen Nutzernamen. Langes Drücken (Handy) oder Rechtsklick (Desktop)
// öffnet ein kleines Menü: "Erwähnen" (kopiert @handle in die Zwischenablage)
// und "Profil ansehen" (öffnet die öffentliche Profilseite /u/[username]).
export default function UserMention({ username, showAt = false, className = "" }: Props) {
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const pressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function startPress() {
    pressTimer.current = setTimeout(() => setMenuOpen(true), 450);
  }
  function cancelPress() {
    if (pressTimer.current) clearTimeout(pressTimer.current);
  }

  async function handleMention() {
    try {
      await navigator.clipboard.writeText(`@${username} `);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      // Zwischenablage evtl. nicht verfügbar — kein hartes Problem
    }
    setMenuOpen(false);
  }

  function handleViewProfile() {
    setMenuOpen(false);
    router.push(`/u/${username}`);
  }

  return (
    <span className="relative inline-block">
      <button
        type="button"
        onTouchStart={startPress}
        onTouchEnd={cancelPress}
        onTouchCancel={cancelPress}
        onContextMenu={(e) => {
          e.preventDefault();
          setMenuOpen(true);
        }}
        onClick={handleViewProfile}
        className={`font-medium text-indigo-300 hover:underline ${className}`}
      >
        {showAt ? "@" : ""}
        {username}
      </button>

      {menuOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
          <div className="absolute left-0 top-full z-50 mt-1 w-44 overflow-hidden rounded-lg border border-white/10 bg-neutral-900 shadow-xl">
            <button
              onClick={handleMention}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-neutral-200 hover:bg-white/5"
            >
              <AtSign className="h-4 w-4 text-neutral-400" />
              {copied ? "Kopiert!" : "Erwähnen"}
            </button>
            <button
              onClick={handleViewProfile}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-neutral-200 hover:bg-white/5"
            >
              <UserIcon className="h-4 w-4 text-neutral-400" />
              Profil ansehen
            </button>
          </div>
        </>
      )}
    </span>
  );
}
