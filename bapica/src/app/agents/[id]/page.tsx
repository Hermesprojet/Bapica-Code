import Link from 'next/link'
import { notFound } from 'next/navigation'
import { ArrowLeft, ArrowRight, Check } from 'lucide-react'
import AGENTS from '@/lib/agents'
import { AGENT_CONTENT } from '@/lib/agent-content'
import { Navbar } from '@/components/landing/navbar'
import { Footer } from '@/components/landing/footer'
import AgentDemoChat from './agent-demo-chat'

export default function AgentPage({ params }: { params: { id: string } }) {
  // Server Component : notFound() ici renvoie un vrai statut HTTP 404
  // pour un id inconnu, avant tout streaming du HTML.
  const agent = AGENTS.find((a) => a.id === params.id)
  if (!agent) {
    notFound()
  }

  const content = AGENT_CONTENT[agent.id]
  const tagline = content?.tagline || agent.description
  const useCases = content?.useCases || []
  const conversation = content?.conversation || []
  const keyResult = content?.keyResult
  const initial = agent.persona?.[0] || '?'

  return (
    <div className="min-h-screen bg-white text-[#111827]">
      <Navbar />

      <main className="pt-24">
        {/* Fil d'ariane */}
        <div className="container mx-auto max-w-5xl px-6">
          <Link href="/agents" className="inline-flex items-center gap-2 text-sm text-[#6B7280] hover:text-[#111827] transition-colors">
            <ArrowLeft className="h-4 w-4" />
            Tous les agents
          </Link>
        </div>

        {/* Hero */}
        <section className="container mx-auto max-w-5xl px-6 pt-8 pb-16">
          <div className="flex flex-col items-start gap-6 md:flex-row md:items-center">
            <div
              className="flex h-20 w-20 items-center justify-center rounded-2xl text-3xl font-bold text-white shadow-md"
              style={{ backgroundImage: `linear-gradient(135deg, ${agent.avatar.from}, ${agent.avatar.to})` }}
            >
              {initial}
            </div>
            <div>
              <h1 className="text-4xl md:text-5xl font-bold text-[#111827]">{agent.persona}</h1>
              <p className="mt-1 text-lg font-medium text-[#2563EB]">{agent.name}</p>
            </div>
          </div>
          <p className="mt-8 max-w-3xl text-xl text-[#374151] leading-relaxed">{tagline}</p>
          <div className="mt-8 flex flex-wrap gap-4">
            <Link
              href="/signup"
              className="inline-flex items-center gap-2 rounded-lg bg-[#2563EB] px-6 py-3 font-semibold text-white hover:bg-[#1D4ED8] transition-colors"
            >
              Essayer gratuitement 15 jours
              <ArrowRight className="h-4 w-4" />
            </Link>
            <a
              href="#essayer"
              className="inline-flex items-center gap-2 rounded-lg border border-[#E5E7EB] px-6 py-3 font-semibold text-[#111827] hover:border-[#D1D5DB] transition-colors"
            >
              Tester {agent.persona} en direct
            </a>
          </div>
        </section>

        {/* Ce que fait l'agent */}
        {useCases.length > 0 && (
          <section className="bg-[#F9FAFB] py-16">
            <div className="container mx-auto max-w-5xl px-6">
              <h2 className="mb-10 text-3xl font-bold text-[#111827]">Ce que fait {agent.persona}</h2>
              <div className="grid gap-6 md:grid-cols-3">
                {useCases.map((uc, i) => (
                  <div key={i} className="rounded-2xl border border-[#E5E7EB] bg-white p-6">
                    <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-[#2563EB]/10 text-[#2563EB]">
                      <Check className="h-5 w-5" />
                    </div>
                    <h3 className="mb-2 font-bold text-[#111827]">{uc.title}</h3>
                    <p className="text-sm text-[#6B7280] leading-relaxed">{uc.desc}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* Exemple concret */}
        {conversation.length > 0 && (
          <section className="py-16">
            <div className="container mx-auto max-w-3xl px-6">
              <h2 className="mb-8 text-3xl font-bold text-[#111827]">En situation réelle</h2>
              <div className="space-y-4">
                {conversation.map((turn, i) => (
                  <div key={i} className={`flex ${turn.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`max-w-[85%] rounded-2xl px-5 py-4 text-sm leading-relaxed ${
                        turn.role === 'user'
                          ? 'bg-[#111827] text-white rounded-br-sm'
                          : 'bg-[#F3F4F6] text-[#111827] rounded-bl-sm'
                      }`}
                    >
                      {turn.text}
                    </div>
                  </div>
                ))}
              </div>
              {keyResult && (
                <div className="mt-8 inline-flex items-center gap-2 rounded-full border border-[#2563EB]/15 bg-[#2563EB]/5 px-5 py-2.5 text-sm font-medium text-[#2563EB]">
                  <Check className="h-4 w-4" />
                  {keyResult}
                </div>
              )}
            </div>
          </section>
        )}

        {/* Chat démo */}
        <section id="essayer" className="scroll-mt-20 bg-[#F9FAFB] py-16">
          <div className="container mx-auto max-w-3xl px-6">
            <h2 className="mb-2 text-3xl font-bold text-[#111827]">Testez {agent.persona} maintenant</h2>
            <p className="mb-8 text-[#6B7280]">3 messages gratuits, sans inscription.</p>
            <AgentDemoChat agent={agent} />
          </div>
        </section>

        {/* CTA final */}
        <section className="py-20">
          <div className="container mx-auto max-w-3xl px-6 text-center">
            <h2 className="text-3xl md:text-4xl font-bold text-[#111827]">
              {agent.persona} et 9 autres agents, prêts à travailler pour vous.
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-lg text-[#6B7280]">
              Essai gratuit 15 jours. Sans carte bancaire. Annulation en un clic.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-4">
              <Link
                href="/signup"
                className="inline-flex items-center gap-2 rounded-lg bg-[#2563EB] px-8 py-4 font-bold text-white hover:bg-[#1D4ED8] transition-colors"
              >
                Démarrer gratuitement
                <ArrowRight className="h-5 w-5" />
              </Link>
              <Link
                href="/agents"
                className="inline-flex items-center gap-2 rounded-lg border border-[#E5E7EB] px-8 py-4 font-semibold text-[#111827] hover:border-[#D1D5DB] transition-colors"
              >
                Voir tous les agents
              </Link>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  )
}
