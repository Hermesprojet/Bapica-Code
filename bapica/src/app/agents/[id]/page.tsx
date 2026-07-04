import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { ArrowRight, ArrowLeft, Check, Sparkles, User } from 'lucide-react'
import AGENTS, { getAgentById, type PlanKey } from '@/lib/agents'
import { AGENT_CONTENT } from '@/lib/agent-content'
import { AgentAvatar } from '@/components/agents/agent-avatar'
import { Navbar } from '@/components/landing/navbar'
import { Footer } from '@/components/landing/footer'

const planLabels: Record<PlanKey, string> = {
  essential: 'Essentiel',
  pro: 'Pro',
}

export function generateStaticParams() {
  return AGENTS.map((agent) => ({ id: agent.id }))
}

export function generateMetadata({ params }: { params: { id: string } }): Metadata {
  const agent = getAgentById(params.id)
  if (!agent) return { title: 'Agent introuvable - Bapica' }
  return {
    title: `${agent.persona} — ${agent.name} | Bapica`,
    description: AGENT_CONTENT[agent.id]?.tagline || agent.description,
  }
}

export default function AgentPage({ params }: { params: { id: string } }) {
  const agent = getAgentById(params.id)
  const content = agent ? AGENT_CONTENT[agent.id] : undefined
  if (!agent || !content) notFound()

  return (
    <>
      <Navbar />
      <main className="pt-16">
        {/* Hero de l'agent */}
        <section className="relative overflow-hidden py-16 md:py-24">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,hsl(var(--primary)/0.12),transparent_55%)]" />
          <div className="container relative mx-auto px-4">
            <Link
              href="/#agents"
              className="mb-8 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="h-4 w-4" /> Tous les agents
            </Link>
            <div className="flex flex-col items-start gap-8 md:flex-row md:items-center">
              <AgentAvatar agent={agent} size={112} className="shrink-0 rounded-full shadow-xl" />
              <div>
                <div className="mb-3 flex flex-wrap items-center gap-3">
                  <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
                    {agent.persona}
                  </h1>
                  <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
                    Formule {planLabels[agent.minPlan]}
                  </span>
                </div>
                <p className="text-lg font-medium text-muted-foreground">{agent.name}</p>
                <p className="mt-3 max-w-2xl text-muted-foreground">{content.tagline}</p>
                <div className="mt-6 flex flex-col gap-3 sm:flex-row">
                  <Link
                    href="/signup"
                    className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-primary px-6 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/25 hover:bg-primary/90 transition-all"
                  >
                    Activer {agent.persona} gratuitement <ArrowRight className="h-4 w-4" />
                  </Link>
                  <Link
                    href="/#demo"
                    className="inline-flex h-11 items-center justify-center rounded-lg border border-border bg-background px-6 text-sm font-medium hover:bg-muted transition-colors"
                  >
                    Essayer la démo
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Cas d'usage */}
        <section className="border-t border-border py-16 md:py-20">
          <div className="container mx-auto px-4">
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
              Ce que {agent.persona} fait pour vous
            </h2>
            <div className="mt-8 grid gap-6 md:grid-cols-3">
              {content.useCases.map((uc) => (
                <div key={uc.title} className="rounded-xl border border-border bg-card p-6">
                  <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                    <Check className="h-4 w-4 text-primary" />
                  </div>
                  <h3 className="font-semibold">{uc.title}</h3>
                  <p className="mt-2 text-sm text-muted-foreground">{uc.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Exemple de conversation */}
        <section className="border-t border-border py-16 md:py-20">
          <div className="container mx-auto px-4">
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
              {agent.persona} en action
            </h2>
            <p className="mt-2 text-muted-foreground">Un exemple d&apos;échange réel.</p>
            <div className="mt-8 max-w-2xl space-y-4">
              {content.conversation.map((msg, i) => (
                <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                  {msg.role === 'assistant' && (
                    <AgentAvatar agent={agent} size={32} className="mt-0.5 shrink-0 rounded-full" />
                  )}
                  <div
                    className={`max-w-[85%] rounded-xl px-4 py-3 text-sm leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-primary text-primary-foreground'
                        : 'border border-border bg-card'
                    }`}
                  >
                    {msg.text}
                  </div>
                  {msg.role === 'user' && (
                    <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
                      <User className="h-4 w-4" />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Résultat clé + CTA final */}
        <section className="border-t border-border py-16 md:py-20">
          <div className="container mx-auto px-4">
            <div className="rounded-2xl gradient-hero px-8 py-14 text-center text-white">
              <Sparkles className="mx-auto mb-4 h-7 w-7 text-white/80" />
              <p className="mx-auto max-w-xl text-2xl font-bold">{content.keyResult}</p>
              <p className="mt-3 text-white/75">
                {agent.persona} est inclus dans la formule {planLabels[agent.minPlan]}, avec{' '}
                {AGENTS.length - 1} autres agents spécialisés.
              </p>
              <Link
                href="/signup"
                className="mt-8 inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-white px-8 text-sm font-medium text-primary shadow-lg hover:bg-white/90 transition-all"
              >
                Commencer gratuitement <ArrowRight className="h-4 w-4" />
              </Link>
            </div>

            {/* Autres agents */}
            <div className="mt-16">
              <h3 className="mb-6 text-lg font-semibold">Découvrez aussi</h3>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {AGENTS.filter((a) => a.id !== agent.id)
                  .slice(0, 4)
                  .map((other) => (
                    <Link
                      key={other.id}
                      href={`/agents/${other.id}`}
                      className="group flex items-center gap-3 rounded-xl border border-border bg-card p-4 hover:border-primary/50 transition-all"
                    >
                      <AgentAvatar agent={other} size={40} className="shrink-0 rounded-full" />
                      <div className="min-w-0">
                        <p className="text-sm font-semibold group-hover:text-primary transition-colors">
                          {other.persona}
                        </p>
                        <p className="truncate text-xs text-muted-foreground">{other.name}</p>
                      </div>
                    </Link>
                  ))}
              </div>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  )
}
