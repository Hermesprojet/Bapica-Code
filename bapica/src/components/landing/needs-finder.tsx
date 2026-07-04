'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ArrowRight, ArrowLeft, RotateCcw, Sparkles, Check } from 'lucide-react'
import { getAgentById, type PlanKey } from '@/lib/agents'
import { AgentAvatar } from '@/components/agents/agent-avatar'

// Secteurs d'activité (adaptent le message de recommandation)
const SECTORS = [
  'E-commerce',
  'Services / Conseil',
  'Commerce local / Artisan',
  'SaaS / Tech',
  'Immobilier',
  'Santé / Bien-être',
  'Autre',
]

// Objectifs → agents recommandés (par ordre de pertinence)
const GOALS: {
  id: string
  label: string
  desc: string
  agents: string[]
}[] = [
  {
    id: 'prospection',
    label: 'Trouver plus de clients',
    desc: 'Prospection et prise de rendez-vous automatisées',
    agents: ['prospector', 'closer'],
  },
  {
    id: 'ventes',
    label: 'Augmenter mon chiffre d’affaires',
    desc: 'Convertir plus, suivre les performances',
    agents: ['closer', 'prospector', 'analytics'],
  },
  {
    id: 'visibilite',
    label: 'Gagner en visibilité',
    desc: 'Contenu, réseaux sociaux, vidéos, tendances',
    agents: ['content', 'video', 'trends'],
  },
  {
    id: 'support',
    label: 'Améliorer mon support client',
    desc: 'Réponses 24/7, standard téléphonique',
    agents: ['support', 'telephone'],
  },
  {
    id: 'admin',
    label: 'Automatiser l’administratif',
    desc: 'Facturation, TVA, contrats, tâches courantes',
    agents: ['accounting', 'legal', 'general'],
  },
  {
    id: 'recrutement',
    label: 'Recruter plus efficacement',
    desc: 'Offres, tri des CV, préqualification',
    agents: ['recruiter'],
  },
]

const SIZES = [
  { id: 'solo', label: 'Solo / Indépendant' },
  { id: 'small', label: 'Petite équipe (2-10)' },
  { id: 'pme', label: 'PME (10+)' },
]

const planLabel: Record<PlanKey, string> = {
  starter: 'Starter',
  pro: 'Pro',
  business: 'Business',
}
const planPrice: Record<PlanKey, number> = { starter: 29, pro: 59, business: 99 }
const planRank: Record<PlanKey, number> = { starter: 0, pro: 1, business: 2 }

export function NeedsFinder() {
  const [step, setStep] = useState(0)
  const [sector, setSector] = useState<string | null>(null)
  const [goals, setGoals] = useState<string[]>([])
  const [size, setSize] = useState<string | null>(null)

  const toggleGoal = (id: string) =>
    setGoals((g) => (g.includes(id) ? g.filter((x) => x !== id) : [...g, id]))

  const reset = () => {
    setStep(0)
    setSector(null)
    setGoals([])
    setSize(null)
  }

  // Calcule les agents recommandés (dédupliqués, ordre de première apparition)
  const recommendedIds = Array.from(
    new Set(GOALS.filter((g) => goals.includes(g.id)).flatMap((g) => g.agents))
  )
  const recommendedAgents = recommendedIds
    .map((id) => getAgentById(id))
    .filter((a): a is NonNullable<ReturnType<typeof getAgentById>> => !!a)

  // Formule recommandée : plan le plus élevé requis par les agents, ajusté à la taille
  let planNeeded: PlanKey = 'starter'
  for (const a of recommendedAgents) {
    if (planRank[a.minPlan] > planRank[planNeeded]) planNeeded = a.minPlan
  }
  if (size === 'pme' && planRank[planNeeded] < planRank['business'])
    planNeeded = 'business'
  else if (size === 'small' && planRank[planNeeded] < planRank['pro'])
    planNeeded = 'pro'

  const canNext =
    (step === 0 && sector) || (step === 1 && goals.length > 0) || (step === 2 && size)
  const totalSteps = 3

  return (
    <section id="diagnostic" className="border-t border-border py-20 md:py-28">
      <div className="container mx-auto px-4">
        <div className="mx-auto mb-10 max-w-2xl text-center">
          <div className="mx-auto mb-4 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-sm">
            <Sparkles className="h-4 w-4 text-primary" />
            <span className="text-muted-foreground">Diagnostic gratuit · 30 secondes</span>
          </div>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Quels agents IA pour <span className="gradient-text">votre activité</span> ?
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Répondez à 3 questions, on vous recommande votre équipe d’agents et la formule adaptée.
          </p>
        </div>

        <div className="mx-auto max-w-3xl rounded-2xl border border-border bg-card p-6 md:p-10">
          {step < totalSteps ? (
            <>
              {/* Progression */}
              <div className="mb-8 flex items-center gap-2">
                {Array.from({ length: totalSteps }).map((_, i) => (
                  <div
                    key={i}
                    className={`h-1.5 flex-1 rounded-full transition-colors ${
                      i <= step ? 'bg-primary' : 'bg-border'
                    }`}
                  />
                ))}
              </div>

              {/* Étape 1 : secteur */}
              {step === 0 && (
                <div>
                  <h3 className="mb-6 text-xl font-semibold">Quelle est votre activité ?</h3>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {SECTORS.map((s) => (
                      <button
                        key={s}
                        onClick={() => setSector(s)}
                        className={`rounded-xl border p-4 text-left text-sm font-medium transition-all ${
                          sector === s
                            ? 'border-primary bg-primary/5 text-primary'
                            : 'border-border hover:border-primary/50'
                        }`}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Étape 2 : objectifs */}
              {step === 1 && (
                <div>
                  <h3 className="mb-2 text-xl font-semibold">Votre objectif prioritaire ?</h3>
                  <p className="mb-6 text-sm text-muted-foreground">Sélectionnez un ou plusieurs objectifs.</p>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {GOALS.map((g) => {
                      const active = goals.includes(g.id)
                      return (
                        <button
                          key={g.id}
                          onClick={() => toggleGoal(g.id)}
                          className={`flex items-start gap-3 rounded-xl border p-4 text-left transition-all ${
                            active
                              ? 'border-primary bg-primary/5'
                              : 'border-border hover:border-primary/50'
                          }`}
                        >
                          <span
                            className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border ${
                              active ? 'border-primary bg-primary text-primary-foreground' : 'border-border'
                            }`}
                          >
                            {active && <Check className="h-3.5 w-3.5" />}
                          </span>
                          <span>
                            <span className="block text-sm font-medium">{g.label}</span>
                            <span className="block text-xs text-muted-foreground">{g.desc}</span>
                          </span>
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Étape 3 : taille */}
              {step === 2 && (
                <div>
                  <h3 className="mb-6 text-xl font-semibold">Quelle est la taille de votre structure ?</h3>
                  <div className="grid gap-3 sm:grid-cols-3">
                    {SIZES.map((s) => (
                      <button
                        key={s.id}
                        onClick={() => setSize(s.id)}
                        className={`rounded-xl border p-4 text-center text-sm font-medium transition-all ${
                          size === s.id
                            ? 'border-primary bg-primary/5 text-primary'
                            : 'border-border hover:border-primary/50'
                        }`}
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Navigation */}
              <div className="mt-8 flex items-center justify-between">
                <button
                  onClick={() => setStep((s) => Math.max(0, s - 1))}
                  disabled={step === 0}
                  className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground disabled:opacity-0 transition-colors"
                >
                  <ArrowLeft className="h-4 w-4" /> Retour
                </button>
                <button
                  onClick={() => setStep((s) => s + 1)}
                  disabled={!canNext}
                  className="inline-flex items-center gap-2 rounded-lg bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40 transition-all"
                >
                  {step === totalSteps - 1 ? 'Voir ma recommandation' : 'Continuer'}
                  <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            </>
          ) : (
            /* Résultat */
            <div>
              <div className="mb-8 text-center">
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                  <Sparkles className="h-6 w-6 text-primary" />
                </div>
                <h3 className="text-2xl font-bold">
                  Votre équipe Bapica sur mesure
                </h3>
                <p className="mt-2 text-muted-foreground">
                  Pour {sector?.toLowerCase()}, voici les agents qui vont vous aider à atteindre vos objectifs.
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                {recommendedAgents.map((agent) => (
                  <div
                    key={agent.id}
                    className="flex items-center gap-3 rounded-xl border border-border bg-background p-4"
                  >
                    <AgentAvatar agent={agent} size={44} className="shrink-0 rounded-full shadow-sm" />
                    <div className="min-w-0">
                      <p className="text-sm font-semibold">{agent.persona}</p>
                      <p className="truncate text-xs text-muted-foreground">{agent.name}</p>
                    </div>
                  </div>
                ))}
              </div>

              {/* Formule recommandée */}
              <div className="mt-8 rounded-xl border border-primary/30 bg-primary/5 p-6 text-center">
                <p className="text-sm text-muted-foreground">Formule recommandée</p>
                <p className="mt-1 text-2xl font-bold">
                  {planLabel[planNeeded]}{' '}
                  <span className="text-base font-normal text-muted-foreground">
                    — {planPrice[planNeeded]}€/mois
                  </span>
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {recommendedAgents.length} agent{recommendedAgents.length > 1 ? 's' : ''} recommandé{recommendedAgents.length > 1 ? 's' : ''} pour votre projet
                </p>
                <div className="mt-6 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
                  <Link
                    href="/signup"
                    className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-primary px-6 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/25 hover:bg-primary/90 transition-all"
                  >
                    Activer ces agents gratuitement <ArrowRight className="h-4 w-4" />
                  </Link>
                  <button
                    onClick={reset}
                    className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-border bg-background px-6 text-sm font-medium hover:bg-muted transition-colors"
                  >
                    <RotateCcw className="h-4 w-4" /> Refaire le test
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
