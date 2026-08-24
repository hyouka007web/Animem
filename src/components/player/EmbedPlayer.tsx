interface EmbedPlayerProps {
  embedUrl: string;
  title: string;
}

// Bettet die externe Hoster-URL sicher per iFrame ein.
// sandbox erlaubt nur das Nötigste (Skripte + eigene Origin fürs Video-UI,
// Vollbild) und blockiert z.B. Top-Level-Navigation/Popups vom Embed aus.
export default function EmbedPlayer({ embedUrl, title }: EmbedPlayerProps) {
  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-xl bg-black">
      <iframe
        src={embedUrl}
        title={title}
        allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
        allowFullScreen
        sandbox="allow-scripts allow-same-origin allow-presentation allow-popups-to-escape-sandbox"
        referrerPolicy="no-referrer"
        loading="lazy"
        className="absolute inset-0 h-full w-full border-0"
      />
    </div>
  );
}
