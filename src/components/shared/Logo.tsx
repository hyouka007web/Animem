interface LogoProps {
  size?: number;
  withWordmark?: boolean;
  className?: string;
}

// Abstraktes "Auge/Fragment"-Symbol: eine facettierte Rautenform mit
// ausgespartem Pupillen-Schlitz in der Mitte — das "Hinter-die-Kulissen-Sehen".
export default function Logo({ size = 28, withWordmark = true, className = "" }: LogoProps) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 48 48"
        fill="none"
        className="shrink-0 animate-glitch"
      >
        <defs>
          <linearGradient id="realmGrad" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#4ce3f0" />
            <stop offset="55%" stopColor="#7c3aed" />
            <stop offset="100%" stopColor="#e0a458" />
          </linearGradient>
        </defs>
        <path
          d="M24 2 L44 24 L24 46 L4 24 Z"
          stroke="url(#realmGrad)"
          strokeWidth="2"
          fill="none"
        />
        <path
          d="M24 14 L34 24 L24 34 L14 24 Z"
          fill="url(#realmGrad)"
          opacity="0.15"
        />
        {/* Pupillen-Schlitz: ausgesparter Raum in der Mitte */}
        <path d="M24 19 L29 24 L24 29 L19 24 Z" fill="#08090f" />
      </svg>
      {withWordmark && (
        <span className="text-lg font-bold tracking-tight text-white">Animem</span>
      )}
    </span>
  );
}
