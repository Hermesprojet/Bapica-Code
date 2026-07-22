import AGENTS from "@/lib/agents"
import {
  Bot,
  HeadphonesIcon,
  FileText,
  Users,
  Phone,
  Building2,
  Calculator,
  Video,
  Search,
  FileCheck,
  BarChart3,
  TrendingUp,
  type LucideIcon,
} from "lucide-react"

// Mappe le nom d'icône stocké dans la config vers le composant Lucide
const iconMap: Record<string, LucideIcon> = {
  Bot,
  HeadphonesIcon,
  FileText,
  Users,
  Phone,
  Building2,
  Calculator,
  Video,
  Search,
  FileCheck,
  BarChart3,
  TrendingUp,
}

// Dégradés statiques (repris de la section agents) pour que Tailwind
// détecte bien les classes au build plutôt que de les purger.
const agentGradients: Record<string, string> = {
  general: "from-indigo-500 to-blue-500",
  support: "from-emerald-500 to-green-500",
  content: "from-indigo-500 to-blue-500",
  'prospection-strategie': "from-emerald-500 to-teal-500",
  closer: "from-rose-500 to-pink-500",
  telephone: "from-cyan-500 to-teal-500",
  accounting: "from-amber-500 to-yellow-500",
  recruiter: "from-indigo-500 to-blue-500",
  legal: "from-slate-500 to-gray-500",
}

// Spécialité courte affichée sous chaque agent
const specialties: Record<string, string> = {
  support: "Support 24/7",
  content: "Contenu & SEO",
  'prospection-strategie': "Croissance & Prospection",
  closer: "Closing vocal",
  telephone: "Standard virtuel",
  accounting: "Comptabilité",
  recruiter: "Recrutement",
  legal: "Juridique & admin",
}

const roleBadge: Record<
  "coordinator" | "specialist" | "analyst",
  { label: string; className: string }
> = {
  coordinator: {
    label: "Coordinateur",
    className:
      "bg-gradient-to-r from-indigo-500 to-blue-500 text-white border-transparent shadow-[0_0_20px_-4px_rgba(99,102,241,0.6)]",
  },
  specialist: {
    label: "Spécialiste",
    className: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  },
  analyst: {
    label: "Analyste",
    className: "bg-teal-500/10 text-teal-400 border-teal-500/20",
  },
}

export function TeamSection() {
  const leo = AGENTS.find((a) => a.teamRole === "coordinator")!
  const members = AGENTS.filter((a) => a.teamRole !== "coordinator")
  const LeoIcon = iconMap[leo.icon] ?? Bot

  return (
    <section
      id="equipe"
      className="relative border-t border-border overflow-hidden py-20 md:py-28"
    >
      {/* Fond dégradé subtil violet/pourpre */}
      <div className="absolute inset-0 bg-gradient-to-b from-indigo-500/[0.06] via-transparent to-blue-500/[0.05]" />
      <div className="absolute inset-0 bg-grid opacity-20" />
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 h-[500px] w-[500px] rounded-full bg-primary/10 blur-[160px]" />

      <div className="container mx-auto px-4 relative">
        {/* En-tête */}
        <div className="mx-auto mb-4 max-w-2xl text-center animate-slide-up">
          <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary mb-6">
            🤝 Travail d&apos;équipe
          </div>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            🤝 Une équipe qui{" "}
            <span className="gradient-text">travaille pour vous</span>
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Chaque agent Bapica est spécialisé, mais c&apos;est en équipe qu&apos;ils
            excellent. Léo orchestre tout en coulisses.
          </p>
        </div>

        {/* Léo au centre — chef d'orchestre */}
        <div className="relative mt-16 flex flex-col items-center">
          <div className="relative flex flex-col items-center animate-slide-up animate-delay-1">
            {/* Halos pulsés */}
            <div className="absolute inset-0 -z-10 flex items-center justify-center">
              <div className="h-40 w-40 rounded-full bg-primary/20 blur-2xl animate-pulse-glow" />
            </div>

            <div className="relative rounded-2xl border border-accent bg-card/80 backdrop-blur px-8 py-6 text-center shadow-[0_0_50px_-12px_rgba(99,102,241,0.5)]">
              <div className={`mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br ${agentGradients[leo.id] ?? "from-indigo-500 to-blue-500"} text-white shadow-lg animate-float`}>
                <LeoIcon className="h-8 w-8" />
              </div>
              <h3 className="text-lg font-bold">{leo.persona}</h3>
              <p className="text-xs text-muted-foreground mb-3">{leo.name}</p>
              <span
                className={`inline-flex items-center rounded-full border px-3 py-1 text-[11px] font-semibold ${roleBadge.coordinator.className}`}
              >
                {roleBadge.coordinator.label}
              </span>
            </div>
          </div>

          {/* Lignes de connexion SVG (chef d'orchestre → équipe) */}
          <svg
            className="pointer-events-none w-full max-w-4xl h-16 md:h-20 text-primary/40"
            viewBox="0 0 1000 100"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <defs>
              <linearGradient id="team-line" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="currentColor" stopOpacity="0.7" />
                <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
              </linearGradient>
            </defs>
            {[80, 300, 500, 700, 920].map((x) => (
              <path
                key={x}
                d={`M500 0 C500 50, ${x} 40, ${x} 100`}
                fill="none"
                stroke="url(#team-line)"
                strokeWidth="1.5"
                strokeDasharray="4 4"
              />
            ))}
          </svg>

          {/* Grille des agents reliés */}
          <div className="grid w-full gap-4 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
            {members.map((agent, index) => {
              const Icon = iconMap[agent.icon] ?? Bot
              const role = roleBadge[agent.teamRole ?? "specialist"]
              const delayClass = (['animate-delay-1','animate-delay-2','animate-delay-3','animate-delay-4'])[index % 4] ?? 'animate-delay-1'
              return (
                <div
                  key={agent.id}
                  className={`group relative flex flex-col items-center rounded-xl border border-border bg-card/60 p-4 text-center backdrop-blur transition-all duration-300 hover:border-accent hover:-translate-y-1 animate-slide-up ${delayClass}`}
                >
                  {/* Point de connexion en haut de la carte */}
                  <span className="absolute -top-1.5 left-1/2 h-3 w-3 -translate-x-1/2 rounded-full bg-primary/60 ring-4 ring-primary/10" />

                  <div
                    className={`mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br ${agentGradients[agent.id] ?? "from-primary to-primary"} text-white shadow-md transition-transform duration-300 group-hover:scale-110`}
                  >
                    <Icon className="h-5 w-5" />
                  </div>
                  <h4 className="text-sm font-semibold leading-tight">
                    {agent.persona}
                  </h4>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">
                    {specialties[agent.id] ?? agent.name}
                  </p>
                  <span
                    className={`mt-3 inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-medium ${role.className}`}
                  >
                    {role.label}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Message clé */}
        <div className="mx-auto mt-14 max-w-2xl text-center animate-slide-up animate-delay-2">
          <div className="rounded-2xl border border-accent bg-gradient-to-br from-indigo-500/10 to-blue-500/10 px-6 py-6">
            <p className="text-base font-medium sm:text-lg">
              Un seul point de contact&nbsp;:{" "}
              <span className="gradient-text font-bold">Léo</span>. Posez-lui
              votre demande, il mobilise l&apos;équipe.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
