"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import {
  Menu,
  X,
  Home,
  Clapperboard,
  Film,
  Grid3x3,
  Bookmark,
  Bell,
  History,
  ListVideo,
  MessagesSquare,
  LifeBuoy,
  ShieldCheck,
  UserCircle,
  User,
  Search,
} from "lucide-react";
import LogoutButton from "./LogoutButton";

interface NavUser {
  username: string;
  role: "OWNER" | "HEAD_ADMIN" | "ADMIN" | "USER";
  isStaff: boolean;
}

interface Counts {
  watchlist: number;
  subscriptions: number;
}

export default function MobileNavDrawer({
  user,
  counts,
}: {
  user: NavUser | null;
  counts: Counts;
}) {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  function close() {
    setOpen(false);
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        aria-label="Menü öffnen"
        className="rounded-lg p-2 text-neutral-300 hover:bg-white/10 hover:text-white"
      >
        <Menu className="h-6 w-6" />
      </button>

      {open && mounted && createPortal(
        <div className="fixed inset-0 z-50 flex">
          {/* Hintergrund abdunkeln, Tap schließt das Menü */}
          <div className="flex-1 bg-black/60" onClick={close} />

          <div className="flex h-full w-80 max-w-[85vw] flex-col overflow-y-auto border-l border-white/10 bg-neutral-950 p-4">
            <div className="mb-4 flex items-center justify-between">
              <span className="text-lg font-bold text-white">Menü</span>
              <button onClick={close} className="rounded-lg p-2 text-neutral-400 hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>

            {user && (
              <Link
                href="/profile"
                onClick={close}
                className="mb-4 flex items-center gap-3 rounded-xl border border-white/10 bg-neutral-900/60 p-3 hover:bg-neutral-900"
              >
                <UserCircle className="h-9 w-9 text-neutral-400" />
                <div>
                  <p className="text-sm font-medium text-white">{user.username}</p>
                  <p className="text-xs text-neutral-500">{user.role}</p>
                </div>
              </Link>
            )}

            <nav className="flex flex-col gap-1">
              <NavLink href="/" icon={Home} label="Startseite" onClick={close} />
              <NavLink href="/search" icon={Search} label="Suche" onClick={close} />
              <NavLink href="/series" icon={Clapperboard} label="Serien" onClick={close} />
              <NavLink href="/movies" icon={Film} label="Filme" onClick={close} />
              <NavLink href="/categories" icon={Grid3x3} label="Kategorien" onClick={close} />

              {user && (
                <>
                  <SectionLabel label="Bibliothek" />
                  <NavLink
                    href="/library?tab=watchlist"
                    icon={Bookmark}
                    label="Watchlist"
                    badge={counts.watchlist}
                    onClick={close}
                  />
                  <NavLink
                    href="/library?tab=subscriptions"
                    icon={Bell}
                    label="Abonniert"
                    badge={counts.subscriptions}
                    onClick={close}
                  />
                  <NavLink href="/library?tab=history" icon={History} label="Verlauf" onClick={close} />
                  <NavLink href="/library?tab=collections" icon={ListVideo} label="Sammlungen" onClick={close} />
                </>
              )}

              <SectionLabel label="Community" />
              <NavLink href="/forum" icon={MessagesSquare} label="Forum" onClick={close} />
              <NavLink href="/support" icon={LifeBuoy} label="Support" onClick={close} />

              {user && (
                <>
                  <SectionLabel label="Konto" />
                  <NavLink href="/profile" icon={User} label="Profil" onClick={close} />
                </>
              )}

              {user?.isStaff && (
                <>
                  <SectionLabel label="Verwaltung" />
                  <NavLink href="/admin" icon={ShieldCheck} label="Admin-Bereich" onClick={close} />
                </>
              )}
            </nav>

            <div className="mt-auto pt-4">
              {user ? (
                <div onClick={close}>
                  <LogoutButton />
                </div>
              ) : (
                <div className="flex gap-2">
                  <Link
                    href="/login"
                    onClick={close}
                    className="flex-1 rounded-lg border border-white/10 px-4 py-2 text-center text-sm text-neutral-200 hover:bg-white/5"
                  >
                    Anmelden
                  </Link>
                  <Link
                    href="/register"
                    onClick={close}
                    className="flex-1 rounded-lg bg-indigo-600 px-4 py-2 text-center text-sm font-medium text-white hover:bg-indigo-500"
                  >
                    Registrieren
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}

function SectionLabel({ label }: { label: string }) {
  return (
    <p className="mb-1 mt-4 px-3 text-xs font-semibold uppercase tracking-wide text-neutral-500">
      {label}
    </p>
  );
}

function NavLink({
  href,
  icon: Icon,
  label,
  badge,
  onClick,
}: {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  badge?: number;
  onClick: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className="flex items-center justify-between rounded-lg px-3 py-2 text-sm text-neutral-200 hover:bg-white/5"
    >
      <span className="flex items-center gap-3">
        <Icon className="h-4 w-4 text-neutral-400" />
        {label}
      </span>
      {!!badge && (
        <span className="rounded-full bg-indigo-600 px-2 py-0.5 text-xs font-medium text-white">
          {badge}
        </span>
      )}
    </Link>
  );
}
