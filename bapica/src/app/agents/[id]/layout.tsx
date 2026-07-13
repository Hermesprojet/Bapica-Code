import type { Metadata } from "next"
import AGENTS from "@/lib/agents"

export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const agent = AGENTS.find((a) => a.id === params.id)

  if (!agent) {
    return { title: "Agent introuvable — Bapica" }
  }

  return {
    title: {
      absolute: `${agent.persona} — ${agent.name} | Agent IA Bapica`,
    },
    description: `${agent.persona} est votre ${agent.name.toLowerCase()} chez Bapica. ${agent.description}. Découvrez comment cet agent IA peut automatiser votre entreprise.`,
  }
}

export default function AgentLayout({ children }: { children: React.ReactNode }) {
  // Le 404 pour un id inconnu est géré dans page.tsx (seul endroit où notFound()
  // fait effectivement renvoyer un statut HTTP 404 pour une route dynamique).
  return children
}
