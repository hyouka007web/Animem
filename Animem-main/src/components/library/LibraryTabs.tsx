"use client";

import Link from "next/link";

const TABS = [
  { key: "watchlist", label: "Watchlist" },
  { key: "subscriptions", label: "Abonniert" },
  { key: "history", label: "Verlauf" },
  { key: "collections", label: "Sammlungen" },
];

export default function LibraryTabs({ active }: { active: string }) {
  return (
    <div className="mb-6 flex gap-2 overflow-x-auto border-b border-white/10 pb-px">
      {TABS.map((tab) => (
        <Link
          key={tab.key}
          href={`/library?tab=${tab.key}`}
          className={`whitespace-nowrap border-b-2 px-3 py-2 text-sm ${
            active === tab.key
              ? "border-indigo-500 text-white"
              : "border-transparent text-neutral-400 hover:text-neutral-200"
          }`}
        >
          {tab.label}
        </Link>
      ))}
    </div>
  );
}
