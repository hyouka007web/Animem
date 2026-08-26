"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import {
  Menu,
  X,
  ArrowLeft,
  LayoutDashboard,
  Clapperboard,
  Film,
  Users,
  MessagesSquare,
  LifeBuoy,
  Settings,
} from "lucide-react";
import { ROLE_LABELS } from "@/lib/permissions";

// Icons dürfen nicht als Funktion vom Server an eine Client-Komponente übergeben werden —
// deshalb hier lokal per Schlüssel auflösen, der Server schickt nur den String-Key.
const ICONS = {
  dashboard: LayoutDashboard,
  series: Clapperboard,
  movies: Film,
  users: Users,
  forum: MessagesSquare,
  tickets: LifeBuoy,
  settings: Settings,
} as const;

export type AdminIconKey = keyof typeof ICONS;

interface NavItem {
  href: string;
  label: string;
  icon: AdminIconKey;
}

export default function AdminShell({
  navItems,
  username,
  role,
  children,
}: {
  navItems: NavItem[];
  username: string;
  role: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-white/10 bg-neutral-900/90 px-4 py-3 backdrop-blur">
        <div>
          <p className="text-sm font-bold">Animem</p>
          <p className="text-xs text-neutral-500">Admin-Bereich</p>
        </div>
        <button onClick={() => setOpen(true)} className="rounded-lg p-2 text-neutral-300 hover:bg-white/10">
          <Menu className="h-5 w-5" />
        </button>
      </header>

      <main className="p-4 md:p-8">{children}</main>

      {open &&
        mounted &&
        createPortal(
          <div className="fixed inset-0 z-50 flex">
            <div className="flex-1 bg-black/60" onClick={() => setOpen(false)} />
            <div className="flex h-full w-72 max-w-[85vw] flex-col overflow-y-auto border-l border-white/10 bg-neutral-950 p-4">
              <div className="mb-4 flex items-center justify-between">
                <span className="text-lg font-bold">Admin-Menü</span>
                <button onClick={() => setOpen(false)} className="text-neutral-400 hover:text-white">
                  <X className="h-5 w-5" />
                </button>
              </div>

              <Link
                href="/"
                onClick={() => setOpen(false)}
                className="mb-4 flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-sm text-neutral-300 hover:bg-white/5"
              >
                <ArrowLeft className="h-4 w-4" /> Zurück zur Webseite
              </Link>

              <nav className="flex flex-1 flex-col gap-1">
                {navItems.map(({ href, label, icon }) => {
                  const Icon = ICONS[icon];
                  return (
                    <Link
                      key={href}
                      href={href}
                      onClick={() => setOpen(false)}
                      className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-neutral-300 hover:bg-white/5 hover:text-white"
                    >
                      <Icon className="h-4 w-4" />
                      {label}
                    </Link>
                  );
                })}
              </nav>

              <div className="mt-4 rounded-lg bg-white/5 px-3 py-3 text-xs">
                <p className="font-medium text-neutral-200">{username}</p>
                <p className="text-neutral-400">{ROLE_LABELS[role as keyof typeof ROLE_LABELS] ?? role}</p>
              </div>
            </div>
          </div>,
          document.body
        )}
    </div>
  );
}
