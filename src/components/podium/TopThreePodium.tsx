"use client";

import Image from "next/image";
import { motion } from "framer-motion";
import { Crown, Star } from "lucide-react";
import { cn } from "@/lib/utils";

// ------------------------------------------------------------
// Typen
// ------------------------------------------------------------

export interface PodiumSeries {
  id: string;
  slug: string;
  title: string;
  thumbnailUrl: string;
  avgRating: number; // 0–10
}

interface TopThreePodiumProps {
  first: PodiumSeries;
  second: PodiumSeries;
  third: PodiumSeries;
}

// ------------------------------------------------------------
// Konfiguration je Rang: Höhe der Stufe, Bildgröße, Akzentfarbe
// ------------------------------------------------------------

const RANK_CONFIG = {
  1: {
    order: "order-2",
    platformHeight: "h-40 md:h-56",
    imageSize: "h-28 w-28 md:h-40 md:w-40",
    glow: "shadow-[0_0_60px_-8px_rgba(224,164,88,0.55)]",
    ring: "ring-[3px] ring-realm-copper",
    badge: "bg-gradient-to-b from-realm-copper-light to-realm-copper text-black",
    plinth: "bg-gradient-to-b from-realm-copper/30 via-realm-violet/15 to-transparent",
    delay: 0.15,
  },
  2: {
    order: "order-1",
    platformHeight: "h-28 md:h-40",
    imageSize: "h-20 w-20 md:h-28 md:w-28",
    glow: "shadow-[0_0_40px_-12px_rgba(76,227,240,0.45)]",
    ring: "ring-2 ring-realm-cyan",
    badge: "bg-gradient-to-b from-realm-cyan to-cyan-600 text-black",
    plinth: "bg-gradient-to-b from-realm-cyan/25 via-realm-cyan/10 to-transparent",
    delay: 0,
  },
  3: {
    order: "order-3",
    platformHeight: "h-20 md:h-28",
    imageSize: "h-16 w-16 md:h-24 md:w-24",
    glow: "shadow-[0_0_30px_-12px_rgba(124,58,237,0.45)]",
    ring: "ring-2 ring-realm-violet/80",
    badge: "bg-gradient-to-b from-violet-400 to-realm-violet text-black",
    plinth: "bg-gradient-to-b from-realm-violet/25 via-realm-violet/10 to-transparent",
    delay: 0.3,
  },
} as const;

function PodiumSlot({
  rank,
  data,
}: {
  rank: 1 | 2 | 3;
  data: PodiumSeries;
}) {
  const cfg = RANK_CONFIG[rank];

  return (
    <div className={cn("flex flex-col items-center", cfg.order)}>
      {/* Thumbnail + Krone */}
      <motion.a
        href={`/series/${data.slug}`}
        className="relative z-10 flex flex-col items-center"
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: cfg.delay, ease: "easeOut" }}
      >
        {rank === 1 && (
          <>
            {/* Pulsierende Aura hinter Platz 1 (Violett <-> Eisblau) */}
            <div className="absolute -inset-8 -z-10 animate-aura-pulse rounded-full bg-gradient-to-br from-realm-violet via-realm-cyan to-realm-copper blur-2xl" />

            {/* Star-Drop-Partikel: fallen einmalig beim Laden herab */}
            <div className="pointer-events-none absolute -top-6 left-1/2 h-16 w-24 -translate-x-1/2">
              {[0, 1, 2, 3].map((i) => (
                <span
                  key={i}
                  className="absolute block h-1 w-1 animate-star-drop rounded-full bg-realm-copper-light"
                  style={{
                    left: `${20 + i * 20}%`,
                    animationDelay: `${0.6 + i * 0.15}s`,
                  }}
                />
              ))}
            </div>

            <motion.div
              className="relative mb-2"
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: [0, -4, 0] }}
              transition={{
                opacity: { delay: 0.5, duration: 0.4 },
                y: { delay: 0.9, duration: 2.4, repeat: Infinity, ease: "easeInOut" },
              }}
            >
              <Crown className="h-8 w-8 text-realm-copper-light md:h-10 md:w-10" fill="currentColor" />
            </motion.div>
          </>
        )}

        <div
          className={cn(
            "relative overflow-hidden rounded-2xl bg-neutral-900",
            cfg.imageSize,
            cfg.glow,
            cfg.ring
          )}
        >
          <Image
            src={data.thumbnailUrl}
            alt={data.title}
            fill
            className="object-cover"
            sizes="200px"
          />
        </div>

        {/* Rang-Badge */}
        <div
          className={cn(
            "-mt-3 flex h-7 w-7 items-center justify-center rounded-full text-sm font-bold md:h-8 md:w-8",
            cfg.badge
          )}
        >
          {rank}
        </div>

        <p className="mt-2 max-w-[9rem] truncate text-center text-sm font-semibold text-neutral-100 md:max-w-[11rem] md:text-base">
          {data.title}
        </p>

        <div className="mt-1 flex items-center gap-1 text-xs text-neutral-400">
          <Star className="h-3.5 w-3.5 fill-realm-copper text-realm-copper" />
          {data.avgRating.toFixed(1)}
        </div>
      </motion.a>

      {/* Treppchen-Stufe */}
      <motion.div
        className={cn(
          "mt-4 w-24 rounded-t-lg border-t border-white/10 md:w-36",
          cfg.platformHeight,
          cfg.plinth
        )}
        initial={{ scaleY: 0 }}
        animate={{ scaleY: 1 }}
        style={{ transformOrigin: "bottom" }}
        transition={{ duration: 0.6, delay: cfg.delay, ease: "easeOut" }}
      />
    </div>
  );
}

export default function TopThreePodium({ first, second, third }: TopThreePodiumProps) {
  return (
    <section className="relative mx-auto w-full max-w-3xl px-4 py-12">
      <h2 className="shimmer-text mb-8 text-center text-2xl font-bold tracking-tight md:text-3xl">
        Die beliebtesten Serien
      </h2>
      <div className="flex items-end justify-center gap-3 md:gap-6">
        <PodiumSlot rank={2} data={second} />
        <PodiumSlot rank={1} data={first} />
        <PodiumSlot rank={3} data={third} />
      </div>
    </section>
  );
}
