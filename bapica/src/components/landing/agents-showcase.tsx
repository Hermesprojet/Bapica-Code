'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import AGENTS from '@/lib/agents'
import { AGENT_CONTENT } from '@/lib/agent-content'

// Slides = un scénario par agent, dans l'ordre de la liste d'agents.
const SLIDES = AGENTS.map((agent) => ({
  agent,
  content: AGENT_CONTENT[agent.id],
})).filter((s) => s.content)

function Avatar({ from, to, initial, size = 'md' }: { from: string; to: string; initial: string; size?: 'md' | 'lg' }) {
  const cls = size === 'lg' ? 'h-14 w-14 text-xl' : 'h-11 w-11 text-base'
  return (
    <div
      className={`${cls} flex shrink-0 items-center justify-center rounded-full font-bold text-white shadow-sm`}
      style={{ backgroundImage: `linear-gradient(135deg, ${from}, ${to})` }}
    >
      {initial}
    </div>
  )
}

export function AgentsShowcase() {
  const [index, setIndex] = useState(0)
  const [paused, setPaused] = useState(false)
  const count = SLIDES.length

  const go = useCallback((next: number) => {
    setIndex(((next % count) + count) % count)
  }, [count])

  useEffect(() => {
    if (paused || count <= 1) return
    const t = setInterval(() => setIndex((i) => (i + 1) % count), 6000)
    return () => clearInterval(t)
  }, [paused, count])

  const active = SLIDES[index]

  return (
    <section id="agents" className="scroll-mt-20 py-24 bg-white">
      <div className="container mx-auto max-w-7xl px-6">
        {/* En-tête */}
        <div className="mb-12 max-w-3xl">
          <p className="text-sm font-medium text-[#2563EB] uppercase tracking-wider mb-4">Agents</p>
          <h2 className="text-4xl md:text-5xl font-bold text-[#111827] mb-4">
            Ce que vos agents font pour vous.
          </h2>
          <p className="text-xl text-[#6B7280]">
            10 spécialistes qui agissent 24/7 : ils contactent, publient, facturent, recrutent.
            Faites défiler pour voir chacun à l&apos;œuvre.
          </p>
        </div>

        {/* Carrousel de scénarios */}
        <div
          className="relative"
          onMouseEnter={() => setPaused(true)}
          onMouseLeave={() => setPaused(false)}
        >
          <div className="rounded-3xl border border-[#E5E7EB] bg-[#F9FAFB] overflow-hidden">
            <div className="grid md:grid-cols-2">
              {/* Identité de l'agent */}
              <div className="p-8 md:p-12 flex flex-col justify-center">
                <div className="flex items-center gap-4 mb-6">
                  <Avatar from={active.agent.avatar.from} to={active.agent.avatar.to} initial={active.agent.persona?.[0] || '?'} size="lg" />
                  <div>
                    <div className="text-2xl font-bold text-[#111827]">{active.agent.persona}</div>
                    <div className="text-sm text-[#6B7280]">{active.agent.name}</div>
                  </div>
                </div>
                <p className="text-lg text-[#374151] leading-relaxed mb-6">{active.content.tagline}</p>
                <div className="inline-flex items-center gap-2 self-start rounded-full bg-[#2563EB]/5 border border-[#2563EB]/15 px-4 py-2 text-sm font-medium text-[#2563EB] mb-8">
                  ✓ {active.content.keyResult}
                </div>
                <Link
                  href={`/agents/${active.agent.id}`}
                  className="inline-flex items-center gap-2 self-start rounded-lg bg-[#111827] px-5 py-3 text-sm font-semibold text-white hover:bg-[#1F2937] transition-colors"
                >
                  Découvrir {active.agent.persona}
                  <ChevronRight className="h-4 w-4" />
                </Link>
              </div>

              {/* Mockup de conversation */}
              <div className="bg-white p-8 md:p-12 border-t md:border-t-0 md:border-l border-[#E5E7EB]">
                <div className="space-y-4">
                  {active.content.conversation.map((turn, i) => (
                    <div key={i} className={`flex ${turn.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div
                        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
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
              </div>
            </div>
          </div>

          {/* Flèches */}
          <button
            type="button"
            aria-label="Agent précédent"
            onClick={() => go(index - 1)}
            className="absolute -left-3 md:-left-5 top-1/2 -translate-y-1/2 flex h-11 w-11 items-center justify-center rounded-full border border-[#E5E7EB] bg-white text-[#111827] shadow-sm hover:bg-[#F9FAFB] transition-colors"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
          <button
            type="button"
            aria-label="Agent suivant"
            onClick={() => go(index + 1)}
            className="absolute -right-3 md:-right-5 top-1/2 -translate-y-1/2 flex h-11 w-11 items-center justify-center rounded-full border border-[#E5E7EB] bg-white text-[#111827] shadow-sm hover:bg-[#F9FAFB] transition-colors"
          >
            <ChevronRight className="h-5 w-5" />
          </button>
        </div>

        {/* Points indicateurs */}
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {SLIDES.map((s, i) => (
            <button
              key={s.agent.id}
              type="button"
              aria-label={`Voir ${s.agent.persona}`}
              onClick={() => go(i)}
              className={`h-2 rounded-full transition-all ${i === index ? 'w-8 bg-[#2563EB]' : 'w-2 bg-[#D1D5DB] hover:bg-[#9CA3AF]'}`}
            />
          ))}
        </div>

        {/* Grille complète des agents */}
        <div className="mt-20">
          <h3 className="text-2xl font-bold text-[#111827] mb-8">Toute l&apos;équipe, en un coup d&apos;œil</h3>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {SLIDES.map(({ agent, content }) => (
              <Link
                key={agent.id}
                href={`/agents/${agent.id}`}
                className="group flex items-start gap-4 rounded-2xl border border-[#E5E7EB] bg-white p-5 hover:border-[#2563EB] hover:shadow-sm transition-all"
              >
                <Avatar from={agent.avatar.from} to={agent.avatar.to} initial={agent.persona?.[0] || '?'} />
                <div className="min-w-0">
                  <div className="font-semibold text-[#111827]">{agent.persona}</div>
                  <div className="text-xs font-medium text-[#2563EB] mb-1.5">{agent.name}</div>
                  <p className="text-sm text-[#6B7280] line-clamp-2">{content.tagline}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
