import Image from "next/image";
import Link from "next/link";
import { Star } from "lucide-react";

interface Props {
  href: string;
  title: string;
  thumb: string;
  rating?: number;
}

// Karte mit "Focus Reveal" (Bild wird beim Hover schärfer, wie ein gelöstes
// Rätsel) und kurzem Glitch-Rand statt einfachem Glow.
export default function PosterCard({ href, title, thumb, rating }: Props) {
  return (
    <Link href={href} className="focus-reveal-group group block">
      <div className="glitch-border relative aspect-[2/3] overflow-hidden rounded-lg bg-midnight-light">
        <Image
          src={thumb}
          alt={title}
          fill
          className="focus-reveal-blur object-cover"
          sizes="200px"
        />
      </div>
      <p className="mt-2 truncate text-sm text-neutral-200 group-hover:text-realm-cyan">{title}</p>
      {typeof rating === "number" && (
        <p className="flex items-center gap-1 text-xs text-neutral-500">
          <Star className="h-3 w-3 fill-realm-copper text-realm-copper" />
          {rating.toFixed(1)}
        </p>
      )}
    </Link>
  );
}
