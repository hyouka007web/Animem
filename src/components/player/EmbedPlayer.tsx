interface EmbedPlayerProps {
  embedUrl: string;
  title: string;
}

function isSafeEmbedUrl(value: string) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password;
  } catch {
    return false;
  }
}

export default function EmbedPlayer({ embedUrl, title }: EmbedPlayerProps) {
  if (!isSafeEmbedUrl(embedUrl)) {
    return (
      <div className="flex aspect-video w-full items-center justify-center rounded-xl bg-black p-6 text-center text-sm text-neutral-400">
        Dieser Video-Link ist nicht sicher konfiguriert. Bitte den Administrator informieren.
      </div>
    );
  }

  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-xl bg-black">
      <iframe
        src={embedUrl}
        title={title}
        allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
        allowFullScreen
        sandbox="allow-scripts allow-same-origin allow-presentation"
        referrerPolicy="no-referrer"
        loading="lazy"
        className="absolute inset-0 h-full w-full border-0"
      />
    </div>
  );
}
