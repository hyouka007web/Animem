import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Animem", template: "%s · Animem" },
  description: "Anime-Serien, Filme, Watchlist, Bewertungen und Community.",
  applicationName: "Animem",
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#09090b",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body className="bg-neutral-950 text-neutral-100 antialiased">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-indigo-600 focus:px-4 focus:py-2 focus:text-white"
        >
          Zum Inhalt springen
        </a>
        <div id="main-content">{children}</div>
      </body>
    </html>
  );
}
