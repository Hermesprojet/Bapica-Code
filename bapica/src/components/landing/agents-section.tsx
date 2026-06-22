import {
  Users,
  Phone,
  FileText,
  Video,
  HeadphonesIcon,
  Building2,
  Search,
  FileCheck,
  Calculator,
  Bot,
  BarChart3,
  ChevronRight,
} from "lucide-react"
import Link from "next/link"

const agents = [
  {
    icon: Users,
    name: "Prospecteur Commercial",
    desc: "Identifie et qualifie des leads B2B, rédige des messages personnalisés.",
    plan: "Pro",
  },
  {
    icon: Phone,
    name: "Closer Vocal",
    desc: "Qualifie par téléphone, traite les objections, convertit en RDV.",
    tools: "Vapi",
    plan: "Pro",
  },
  {
    icon: FileText,
    name: "Créateur de Contenu",
    desc: "Articles SEO, posts réseaux, newsletters, scripts vidéo.",
    plan: "Starter",
  },
  {
    icon: Video,
    name: "Créateur Vidéo IA",
    desc: "Vidéos promotionnelles, Reels, avatars IA multilingues.",
    tools: "HeyGen",
    plan: "Business",
  },
  {
    icon: HeadphonesIcon,
    name: "Support Client",
    desc: "24/7, multilingue, escalade humaine si nécessaire.",
    plan: "Starter",
  },
  {
    icon: Building2,
    name: "Agent Téléphonique",
    desc: "Standard virtuel intelligent, routage, prise de messages.",
    tools: "Twilio",
    plan: "Pro",
  },
  {
    icon: Search,
    name: "Recruteur IA",
    desc: "Rédaction d'offres, tri CV, présélection vocale, entretiens.",
    plan: "Business",
  },
  {
    icon: FileCheck,
    name: "Administratif & Juridique",
    desc: "Contrats, CGV, RGPD, mentions légales, analyse documents.",
    plan: "Business",
  },
  {
    icon: Calculator,
    name: "Agent Comptabilité",
    desc: "Factures, relances impayés, TVA, tableau de bord financier.",
    tools: "Stripe",
    plan: "Pro",
  },
  {
    icon: Bot,
    name: "Agent Général",
    desc: "Point d'entrée universel. Posez n'importe quelle question.",
    plan: "Starter",
  },
  {
    icon: BarChart3,
    name: "Analytics & Reporting",
    desc: "Dashboards, tendances, prédictions, recommandations data.",
    plan: "Business",
  },
]

export function AgentsSection() {
  return (
    <section id="agents" className="py-20 md:py-28">
      <div className="container mx-auto px-4">
        <div className="mx-auto mb-16 max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Une équipe de <span className="gradient-text">11 agents spécialisés</span>
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Chaque agent a une mission précise. Ensemble, ils couvrent tous les aspects de votre activité.
          </p>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {agents.map((agent) => (
            <div
              key={agent.name}
              className="group relative rounded-xl border border-border bg-card p-6 hover:border-primary/50 transition-all hover:shadow-lg hover:shadow-primary/5"
            >
              <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <agent.icon className="h-5 w-5" />
              </div>
              <h3 className="mb-2 font-semibold">{agent.name}</h3>
              <p className="text-sm text-muted-foreground">{agent.desc}</p>
              <div className="mt-4 flex items-center justify-between">
                <span className="inline-flex items-center rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
                  {agent.plan}
                </span>
                {agent.tools && (
                  <span className="text-xs text-muted-foreground">{agent.tools}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
