import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Animem",
  description: "Video-Streaming & Series-Management über externe Video-Embeds.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body className="bg-neutral-950 text-neutral-100 antialiased">{children}</body>
    </html>
  );
}
