import Link from "next/link"
import AGENTS, { type PlanKey } from "@/lib/agents"
import { AgentAvatar } from "@/components/agents/agent-avatar"

const planLabels: Record<PlanKey, string> = {
  essential: 'Essentiel',
  pro: 'Pro',
}

const agentGradients: Record<string, string> = {
  general: 'from-indigo-500 to-blue-500',
  support: 'from-emerald-500 to-green-500',
  content: 'from-indigo-500 to-blue-500',
  'prospection-strategie': 'from-emerald-500 to-teal-500',
  closer: 'from-rose-500 to-pink-500',
  telephone: 'from-cyan-500 to-teal-500',
  accounting: 'from-amber-500 to-yellow-500',
  recruiter: 'from-indigo-500 to-blue-500',
  legal: 'from-slate-500 to-gray-500',
  analytics: 'from-teal-500 to-emerald-500',
  trends: 'from-lime-500 to-green-500',
  scaling: 'from-purple-500 to-violet-500',
}

const replacesData: Record<string, { tool: string; cost: string }> = {
  general: { tool: 'Un assistant de direction', cost: '2500€/mois' },
  support: { tool: 'Zendesk, Intercom, 1 support agent', cost: '3000€/mois' },
  content: { tool: 'Un rédacteur SEO + community manager', cost: '3500€/mois' },
  'prospection-strategie': { tool: 'Apollo, Zoominfo, un SDR', cost: '4000€/mois' },
  closer: { tool: 'Un closer commercial', cost: '5000€/mois' },
  telephone: { tool: 'Un standardiste + standard pro', cost: '2500€/mois' },
  accounting: { tool: 'Un comptable à temps partiel', cost: '1500€/mois' },
  recruiter: { tool: 'Un chasseur de têtes junior', cost: '3000€/mois' },
  legal: { tool: 'Un juriste à temps partiel', cost: '2000€/mois' },
  analytics: { tool: 'Un data analyst + BI tool', cost: '3500€/mois' },
  trends: { tool: 'Une veille marché manuelle', cost: '1000€/mois' },
  scaling: { tool: 'Un consultant en stratégie', cost: '5000€/mois' },
}

export function AgentsSection() {
  return (
    <section id="agents" className="relative border-t border-border py-20 md:py-28 overflow-hidden">
      <div className="absolute inset-0 bg-grid opacity-30" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-[600px] w-[600px] rounded-full bg-primary/5 blur-[150px]" />
      
      <div className="container mx-auto px-4 relative">
        <div className="mx-auto mb-4 max-w-2xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary mb-6">
            🤖 {AGENTS.length} agents IA
          </div>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Une équipe d&apos; <span className="gradient-text">experts IA</span>{" "}
            à votre service
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Chaque agent est spécialisé dans un domaine. Choisissez ceux qui correspondent à vos besoins.
          </p>
        </div>

        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 mt-12">
          {AGENTS.map((agent, index) => (
            <Link
              key={agent.id}
              href={`/agents/${agent.id}`}
              className="agent-card group relative block rounded-xl border border-border bg-card p-5 overflow-hidden hover:border-primary/50 transition-colors"
            >
              {/* Hover gradient effect */}
              <div className={`absolute inset-0 bg-gradient-to-br ${agentGradients[agent.id] || 'from-primary to-primary'} opacity-0 group-hover:opacity-5 transition-opacity duration-500`} />
              
              <div className="relative z-10">
                {/* Agent avatar + name row */}
                <div className="flex items-center gap-3 mb-3">
                  <div className={`flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br ${agentGradients[agent.id] || 'from-primary to-primary'} text-white text-sm font-bold shadow-md`}>
                    {agent.persona.charAt(0)}
                  </div>
                  <div>
                    <h3 className="font-semibold text-sm">{agent.name}</h3>
                    <p className="text-xs text-muted-foreground">{agent.persona}</p>
                  </div>
                </div>

                {/* Description */}
                <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2 mb-3">
                  {agent.description}
                </p>

                {/* Plan badge */}
                <div className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-medium ${
                  agent.minPlan === 'essential'
                    ? 'bg-indigo-500/10 text-indigo-400'
                    : 'bg-blue-500/10 text-blue-400'
                }`}>
                  {planLabels[agent.minPlan]}
                </div>

                {/* Remplace tag */}
                {replacesData[agent.id] && (
                  <div className="mt-2 pt-2 border-t border-border/50">
                    <span className="text-[10px] text-muted-foreground/40 uppercase tracking-wider">Remplace</span>
                    <p className="text-[10px] text-green-600 font-medium">{replacesData[agent.id].tool}</p>
                    <p className="text-[10px] text-muted-foreground/40">Économie : {replacesData[agent.id].cost}</p>
                  </div>
                )}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </section>
  )
}
