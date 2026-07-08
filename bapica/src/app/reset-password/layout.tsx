import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Nouveau mot de passe",
  description: "Créez un nouveau mot de passe sécurisé pour votre compte Bapica.",
}

export default function ResetPasswordLayout({ children }: { children: React.ReactNode }) {
  return children
}
