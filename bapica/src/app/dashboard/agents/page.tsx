import { Metadata } from 'next'
import Link from 'next/link'
import { Sparkles } from 'lucide-react'
import AGENTS, { type PlanKey } from '@/lib/agents'
import { AgentAvatar } from '@/components/agents/agent-avatar'

export const metadata: Metadata = {
  title: 'Mes agents - Bapica',
}

const planLabels: Record<PlanKey, string> = {
  starter: 'Starter',
  pro: 'Pro',
  business: 'Business',
}

const planColors: Record<PlanKey, string> = {
  starter: 'bg-blue-500/10 text-blue-500',
  pro: 'bg-orange-500/10 text-orange-500',
  business: 'bg-purple-500/10 text-purple-500',
}

export default function AgentsPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Mes agents</h1>
        <p className="mt-1 text-muted-foreground">
          Votre équipe d&apos;agents IA. Sélectionnez-en un pour commencer à travailler.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {AGENTS.map((agent) => (
          <Link
            key={agent.id}
            href={`/dashboard/agents/${agent.id}`}
            className="group relative rounded-xl border border-border bg-card p-5 hover:border-primary/50 transition-all hover:shadow-lg hover:-translate-y-0.5"
          >
            <div className="flex items-start gap-3">
              <AgentAvatar agent={agent} size={52} className="shrink-0 rounded-full shadow-md" />
              <div className="min-w-0">
                <h3 className="font-semibold leading-tight group-hover:text-primary transition-colors">
                  {agent.persona}
                </h3>
                <p className="text-sm text-muted-foreground">{agent.name}</p>
              </div>
            </div>
            <p className="mt-3 text-sm text-muted-foreground line-clamp-2">
              {agent.description}
            </p>
            <div className="mt-3 flex items-center justify-between">
              <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${planColors[agent.minPlan]}`}>
                {planLabels[agent.minPlan]}
              </span>
              <Sparkles className="h-4 w-4 text-muted-foreground/30 group-hover:text-primary/50 transition-colors" />
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
