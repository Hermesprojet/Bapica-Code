'use client'

import { useState, useEffect, useCallback, useRef } from 'react'

const SCENES = 8
const SCENE_DURATION = 7000

const sceneData = [
  {
    label: 'Présentation',
    title: <>Des agents IA qui <span className="bg-gradient-to-r from-[#2dd4bf] to-[#0082e6] bg-clip-text text-transparent">comprennent votre business</span></>,
    subtitle: '13 agents spécialisés. Une plateforme. Zéro configuration.',
  },
  {
    label: 'Le constat',
    title: <><span className="bg-gradient-to-r from-[#2dd4bf] to-[#0082e6] bg-clip-text text-transparent">32 heures</span> par semaine perdues</>,
    cards: [
      { icon: '📞', title: 'Appels manqués', desc: 'Chaque appel sans réponse = un client perdu.' },
      { icon: '📧', title: 'Admin chronophage', desc: 'Factures, relances, devis — des heures chaque jour.' },
      { icon: '🔍', title: 'Prospection lente', desc: 'Trouver des leads sans outil prend 70% du temps.' },
    ],
  },
  {
    label: 'La solution',
    title: <>Une équipe d&apos;agents IA qui <span className="bg-gradient-to-r from-[#2dd4bf] to-[#0082e6] bg-clip-text text-transparent">travaille pour vous</span></>,
    agents: [
      { letter: 'L', name: 'Léo', role: 'Coordinateur', gradient: 'from-blue-500 to-indigo-600' },
      { letter: 'S', name: 'Sofia', role: 'Support Client', gradient: 'from-emerald-500 to-green-600' },
      { letter: 'M', name: 'Marc', role: 'Commercial', gradient: 'from-amber-500 to-orange-600' },
      { letter: 'R', name: 'Roxane', role: 'Croissance', gradient: 'from-violet-500 to-purple-600' },
      { letter: 'C', name: 'Camille', role: 'Contenu & SEO', gradient: 'from-pink-500 to-rose-600' },
      { letter: 'H', name: 'Hugo', role: 'Téléphone', gradient: 'from-cyan-500 to-teal-600' },
    ],
  },
  {
    label: 'Intelligence',
    title: <>Pas de configuration. <span className="bg-gradient-to-r from-[#2dd4bf] to-[#0082e6] bg-clip-text text-transparent">L&apos;IA comprend</span> automatiquement.</>,
    stats: [
      { value: '5 min', label: 'pour analyser votre business' },
      { value: '72/100', label: 'score de maturité calculé' },
      { value: '3', label: 'agents recommandés automatiquement' },
    ],
  },
  {
    label: 'Résultats',
    title: <>Mesurable. <span className="bg-gradient-to-r from-[#2dd4bf] to-[#0082e6] bg-clip-text text-transparent">Immédiat.</span></>,
    stats: [
      { value: '3×', label: 'plus de leads qualifiés' },
      { value: '32h', label: 'économisées / semaine' },
      { value: '−80%', label: 'de coûts vs un employé' },
    ],
  },
  {
    label: 'Pourquoi Bapica',
    title: <><span className="bg-gradient-to-r from-[#2dd4bf] to-[#0082e6] bg-clip-text text-transparent">13 agents</span> coordonnés. Une seule plateforme.</>,
    cards: [
      { icon: '🧠', title: 'IA Supérieure', desc: 'Claude Sonnet vs GPT-4o-mini — la qualité fait la différence.' },
      { icon: '📊', title: 'Business Intelligence', desc: 'Seule plateforme avec analyse stratégique et ROI.' },
      { icon: '🤝', title: 'Coordination native', desc: "Léo orchestre l'équipe. Les concurrents ont des agents isolés." },
    ],
  },
  {
    label: 'Tarifs',
    title: <>Simple. <span className="bg-gradient-to-r from-[#2dd4bf] to-[#0082e6] bg-clip-text text-transparent">Transparent.</span></>,
    pricing: true,
  },
  {
    label: 'C\'est parti',
    title: <>Prêt à automatiser <span className="bg-gradient-to-r from-[#2dd4bf] to-[#0082e6] bg-clip-text text-transparent">votre croissance</span> ?</>,
    subtitle: '15 jours d\'essai gratuit. Sans CB. 5 minutes de configuration.',
    cta: true,
  },
]

export function VideoPresentation() {
  const [current, setCurrent] = useState(0)
  const [autoPlaying, setAutoPlaying] = useState(true)
  const timerRef = useRef<NodeJS.Timeout | null>(null)
  const [key, setKey] = useState(0) // Force re-render for animations

  const goTo = useCallback((n: number) => {
    setCurrent((n + SCENES) % SCENES)
    setKey(k => k + 1)
  }, [])

  const next = useCallback(() => goTo(current + 1), [current, goTo])
  const prev = useCallback(() => goTo(current - 1), [current, goTo])

  useEffect(() => {
    if (!autoPlaying) return
    timerRef.current = setTimeout(() => {
      setCurrent(c => (c + 1) % SCENES)
      setKey(k => k + 1)
    }, SCENE_DURATION)
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [current, autoPlaying])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === ' ') { e.preventDefault(); next() }
      if (e.key === 'ArrowLeft') { e.preventDefault(); prev() }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [next, prev])

  const scene = sceneData[current]

  return (
    <div className="relative flex min-h-[600px] items-center justify-center overflow-hidden rounded-2xl border border-white/[0.06] bg-[#0d0d1a] py-16 sm:min-h-[700px]" key={key}>
      {/* Progress bar */}
      <div className="absolute top-0 left-0 h-0.5 bg-[#0082e6] transition-all duration-300" style={{ width: `${((current + 1) / SCENES) * 100}%` }} />

      {/* Logo */}
      <span className="absolute top-6 left-6 text-lg font-bold tracking-tight z-10">Bapica</span>

      {/* Scene number */}
      <span className="absolute top-6 right-6 text-xs text-white/30 z-10">{current + 1} / {SCENES}</span>

      <div className="relative z-10 flex max-w-4xl flex-col items-center px-6 text-center">
        {/* Label */}
        <span className="mb-4 inline-flex items-center rounded-full border border-[#2dd4bf]/20 bg-[#2dd4bf]/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.15em] text-[#2dd4bf] animate-fade-in">
          {scene.label}
        </span>

        {/* Title */}
        <h2 className="animate-fade-in text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl [animation-delay:150ms]" style={{ letterSpacing: '-0.03em', lineHeight: 1.1 }}>
          {scene.title}
        </h2>

        {/* Subtitle */}
        {scene.subtitle && (
          <p className="mt-4 animate-fade-in text-base text-white/50 sm:text-lg [animation-delay:300ms] max-w-lg">
            {scene.subtitle}
          </p>
        )}

        {/* Cards */}
        {scene.cards && (
          <div className="mt-10 grid w-full gap-4 sm:grid-cols-3">
            {scene.cards.map((card, i) => (
              <div key={i} className="animate-scale-in rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 text-left" style={{ animationDelay: `${300 + i * 150}ms` }}>
                <div className="mb-3 text-2xl">{card.icon}</div>
                <h3 className="mb-2 text-base font-semibold">{card.title}</h3>
                <p className="text-sm text-white/40">{card.desc}</p>
              </div>
            ))}
          </div>
        )}

        {/* Agents grid */}
        {scene.agents && (
          <div className="mt-10 grid w-full max-w-2xl gap-3 sm:grid-cols-2">
            {scene.agents.map((agent, i) => (
              <div key={i} className="animate-slide-in flex items-center gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3" style={{ animationDelay: `${200 + i * 100}ms` }}>
                <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br ${agent.gradient} text-sm font-bold text-white`}>
                  {agent.letter}
                </div>
                <div className="text-left">
                  <div className="text-sm font-semibold">{agent.name}</div>
                  <div className="text-xs text-white/40">{agent.role}</div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Stats */}
        {scene.stats && (
          <div className="mt-10 flex flex-wrap justify-center gap-8 sm:gap-12">
            {scene.stats.map((stat, i) => (
              <div key={i} className="animate-count-up text-center" style={{ animationDelay: `${300 + i * 200}ms` }}>
                <div className="text-4xl font-bold tracking-tight text-[#2dd4bf] sm:text-5xl">{stat.value}</div>
                <div className="mt-2 text-sm text-white/40">{stat.label}</div>
              </div>
            ))}
          </div>
        )}

        {/* Pricing */}
        {scene.pricing && (
          <div className="mt-10 flex gap-4">
            <div className="animate-scale-in rounded-2xl border border-white/[0.06] bg-white/[0.02] p-8 text-center w-56" style={{ animationDelay: '300ms' }}>
              <div className="text-sm text-white/40 mb-3">Essentiel</div>
              <div className="text-3xl font-bold">49€<span className="text-sm font-normal text-white/40">/mois</span></div>
              <div className="mt-4 text-sm text-white/40">8 agents IA<br />Messages illimités</div>
            </div>
            <div className="animate-scale-in relative rounded-2xl border border-[#0082e6]/30 bg-gradient-to-b from-[#0082e6]/10 to-white/[0.02] p-8 text-center w-56" style={{ animationDelay: '500ms' }}>
              <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-[#0082e6] px-3 py-1 text-[11px] font-semibold text-white">Recommandé</span>
              <div className="text-sm text-white/40 mb-3">Pro</div>
              <div className="text-3xl font-bold">79€<span className="text-sm font-normal text-white/40">/mois</span></div>
              <div className="mt-4 text-sm text-white/40">13 agents IA<br />Appels 0,20€/min</div>
            </div>
          </div>
        )}

        {/* CTA */}
        {scene.cta && (
          <a href="/signup" className="mt-8 animate-fade-in inline-flex items-center gap-2 rounded-xl bg-[#0082e6] px-8 py-4 text-lg font-semibold text-white shadow-lg shadow-[#0082e6]/25 transition-all hover:bg-[#0073cc] [animation-delay:400ms]">
            Commencer gratuitement →
          </a>
        )}
      </div>

      {/* Glow */}
      <div className="pointer-events-none absolute top-1/2 left-1/2 h-[500px] w-[500px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#2dd4bf] opacity-[0.04] blur-[100px]" />

      {/* Controls */}
      <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-2">
        <button onClick={prev} className="rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-1.5 text-sm text-white/60 hover:bg-white/[0.08]">←</button>
        {Array.from({ length: SCENES }).map((_, i) => (
          <button
            key={i}
            onClick={() => goTo(i)}
            className={`rounded-full transition-all ${i === current ? 'h-1.5 w-6 bg-[#0082e6]' : 'h-1.5 w-1.5 bg-white/15'}`}
          />
        ))}
        <button onClick={next} className="rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-1.5 text-sm text-white/60 hover:bg-white/[0.08]">→</button>
        <button
          onClick={() => setAutoPlaying(!autoPlaying)}
          className="ml-2 rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-1.5 text-xs text-white/60 hover:bg-white/[0.08]"
        >
          {autoPlaying ? '⏸' : '▶'}
        </button>
      </div>

      <style jsx>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(16px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes scaleIn {
          from { opacity: 0; transform: scale(0.9); }
          to { opacity: 1; transform: scale(1); }
        }
        @keyframes slideIn {
          from { opacity: 0; transform: translateX(-12px); }
          to { opacity: 1; transform: translateX(0); }
        }
        @keyframes countUp {
          from { opacity: 0; filter: blur(8px); transform: translateY(8px); }
          to { opacity: 1; filter: blur(0); transform: translateY(0); }
        }
        .animate-fade-in { animation: fadeIn 0.6s ease-out both; }
        .animate-scale-in { animation: scaleIn 0.5s ease-out both; }
        .animate-slide-in { animation: slideIn 0.4s ease-out both; }
        .animate-count-up { animation: countUp 0.8s ease-out both; }
      `}</style>
    </div>
  )
}
