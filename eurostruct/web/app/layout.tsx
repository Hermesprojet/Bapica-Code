import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "EUROSTRUCT — vérification EC2",
  description:
    "Vérification ELU en flexion simple, section rectangulaire, Eurocode 2 " +
    "avec Annexe Nationale.",
};

export default function RacineLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
