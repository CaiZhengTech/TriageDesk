import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TriageDesk Console",
  description: "Glass-box ops console for the TriageDesk triage agent",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
