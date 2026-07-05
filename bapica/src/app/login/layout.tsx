import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Connexion — Bapica",
  description: "Connectez-vous à votre compte Bapica pour accéder à vos agents IA.",
}

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return children
}
