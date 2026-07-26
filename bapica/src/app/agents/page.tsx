import type { Metadata } from 'next'
import Link from 'next/link'
import { ArrowRight } from 'lucide-react'
import AGENTS from '@/lib/agents'
import { AGENT_CONTENT } from '@/lib/agent-content'
import { Navbar } from '@/components/landing/navbar'
import { Footer } from '@/components/landing/footer'

export const metadata: Metadata = {
  title: 'Nos agents IA',
  description:
    "Découvrez les 11 agents IA de Bapica : prospection, closing vocal, contenu/SEO, vidéo, comptabilité, support, téléphone, recrutement, juridique, analyse de données et orchestration. Chacun agit 24/7 pour votre PME.",
}

export default function AgentsIndexPage() {
  return (
    <div className="min-h-screen bg-white text-[#111827]">
      <Navbar />

      <main className="pt-24">
        {/* En-tête */}
        <section className="container mx-auto max-w-6xl px-6 pt-8 pb-14">
          <p className="text-sm font-medium text-[#2563EB] uppercase tracking-wider mb-4">Agents</p>
          <h1 className="text-4xl md:text-6xl font-bold text-[#111827] mb-6 leading-tight">
            11 agents spécialisés,<br />
            <span className="text-[#2563EB]">une seule équipe.</span>
          </h1>
          <p className="max-w-2xl text-xl text-[#6B7280]">
            Chaque agent a un métier précis et agit 24/7. Cliquez sur un agent pour voir ce qu&apos;il
            fait concrètement et le tester en direct.
          </p>
        </section>

        {/* Grille des agents */}
        <section className="container mx-auto max-w-6xl px-6 pb-24">
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {AGENTS.map((agent) => {
              const content = AGENT_CONTENT[agent.id]
              const tagline = content?.tagline || agent.description
              const initial = agent.persona?.[0] || '?'
              return (
                <Link
                  key={agent.id}
                  href={`/agents/${agent.id}`}
                  className="group flex flex-col rounded-2xl border border-[#E5E7EB] bg-white p-6 hover:border-[#2563EB] hover:shadow-md transition-all"
                >
                  <div className="mb-4 flex items-center gap-4">
                    <div
                      className="flex h-12 w-12 items-center justify-center rounded-full text-lg font-bold text-white shadow-sm"
                      style={{ backgroundImage: `linear-gradient(135deg, ${agent.avatar.from}, ${agent.avatar.to})` }}
                    >
                      {initial}
                    </div>
                    <div>
                      <div className="font-bold text-[#111827]">{agent.persona}</div>
                      <div className="text-xs font-medium text-[#2563EB]">{agent.name}</div>
                    </div>
                  </div>
                  <p className="flex-1 text-sm text-[#6B7280] leading-relaxed">{tagline}</p>
                  <span className="mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-[#111827] group-hover:text-[#2563EB] transition-colors">
                    Découvrir {agent.persona}
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                  </span>
                </Link>
              )
            })}
          </div>
        </section>

        {/* CTA */}
        <section className="bg-[#111827] py-20">
          <div className="container mx-auto max-w-3xl px-6 text-center">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              Mettez toute l&apos;équipe au travail.
            </h2>
            <p className="mx-auto mb-8 max-w-xl text-lg text-[#9CA3AF]">
              Essai gratuit 15 jours. Sans carte bancaire.
            </p>
            <Link
              href="/signup"
              className="inline-flex items-center gap-2 rounded-lg bg-[#2563EB] px-8 py-4 font-bold text-white hover:bg-[#1D4ED8] transition-colors"
            >
              Démarrer gratuitement
              <ArrowRight className="h-5 w-5" />
            </Link>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  )
}
