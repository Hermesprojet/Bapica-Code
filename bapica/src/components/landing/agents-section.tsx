import AGENTS, { type PlanKey } from "@/lib/agents"
import { AgentAvatar } from "@/components/agents/agent-avatar"

const planLabels: Record<PlanKey, string> = {
  starter: "Starter",
  pro: "Pro",
  business: "Business",
}

export function AgentsSection() {
  return (
    <section id="agents" className="py-20 md:py-28">
      <div className="container mx-auto px-4">
        <div className="mx-auto mb-16 max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Une équipe de <span className="gradient-text">12 agents spécialisés</span>
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Chaque agent a une mission précise. Ensemble, ils couvrent tous les aspects de votre activité.
          </p>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {AGENTS.map((agent) => (
            <div
              key={agent.id}
              className="group relative rounded-xl border border-border bg-card p-6 hover:border-primary/50 transition-all hover:shadow-lg hover:shadow-primary/5"
            >
              <div className="flex items-center gap-3">
                <AgentAvatar agent={agent} size={48} className="shrink-0 rounded-full shadow-md" />
                <div className="min-w-0">
                  <h3 className="font-semibold leading-tight">{agent.persona}</h3>
                  <p className="text-sm text-muted-foreground">{agent.name}</p>
                </div>
              </div>
              <p className="mt-4 text-sm text-muted-foreground">{agent.description}</p>
              <div className="mt-4 flex items-center justify-between">
                <span className="inline-flex items-center rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
                  {planLabels[agent.minPlan]}
                </span>
                <span className="text-xs text-muted-foreground capitalize">
                  {agent.tools[0]?.replace(/_/g, " ")}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
