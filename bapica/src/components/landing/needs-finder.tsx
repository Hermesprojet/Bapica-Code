'use client'

import { useState } from 'react'
import Link from 'next/link'
import {
  ArrowRight,
  ArrowLeft,
  RotateCcw,
  Sparkles,
  Check,
  Clock,
  Globe,
  Wrench,
  Target,
  Building2,
  BarChart3,
  Users,
  MessageSquare,
  FileText,
  Search,
  HeadphonesIcon,
  Bot,
} from 'lucide-react'
import { getAgentById, type PlanKey, type AgentConfig } from '@/lib/agents'
import { AgentAvatar } from '@/components/agents/agent-avatar'

// ─── Questions ──────────────────────────────────────────────────────────────

const SECTORS = [
  'E-commerce',
  'Services / Conseil',
  'Commerce local / Artisan',
  'SaaS / Tech',
  'Immobilier',
  'Santé / Bien-être',
  'Formation / Coaching',
  'Autre',
]

const SIZES = [
  { id: 'solo', label: 'Solo / Indépendant' },
  { id: 'small', label: 'Petite équipe (2-10)' },
  { id: 'pme', label: 'PME (10+)' },
]

// Objectifs prioritaires (max 3)
const GOALS = [
  {
    id: 'prospection',
    label: 'Trouver plus de clients',
    desc: 'Prospection, leads, prise de rendez-vous',
    agents: ['prospector', 'closer'],
    icon: Users,
  },
  {
    id: 'ventes',
    label: 'Augmenter mon chiffre d\'affaires',
    desc: 'Conversion, suivi commercial, closing',
    agents: ['closer', 'prospector', 'analytics'],
    icon: TrendingUp,
  },
  {
    id: 'visibilite',
    label: 'Gagner en visibilité',
    desc: 'Réseaux sociaux, contenu, vidéos, SEO',
    agents: ['content', 'video', 'trends'],
    icon: Target,
  },
  {
    id: 'support',
    label: 'Améliorer mon service client',
    desc: 'Support 24/7, réponse instantanée, satisfaction',
    agents: ['support', 'telephone'],
    icon: HeadphonesIcon,
  },
  {
    id: 'automatisation',
    label: 'Automatiser les tâches répétitives',
    desc: 'Admin, facturation, contrats, process',
    agents: ['accounting', 'legal', 'general'],
    icon: Bot,
  },
  {
    id: 'recrutement',
    label: 'Recruter plus efficacement',
    desc: 'Tri des CV, présélection, entretiens',
    agents: ['recruiter'],
    icon: Search,
  },
  {
    id: 'data',
    label: 'Piloter par la donnée',
    desc: 'Dashboards, KPIs, tendances marché',
    agents: ['analytics', 'trends'],
    icon: BarChart3,
  },
]

// Tâches chronophages (max 3)
const TIME_WASTERS = [
  {
    id: 'admin_tasks',
    label: 'Administratif & paperasse',
    desc: 'Factures, relances, contrats, compta',
    agents: ['accounting', 'legal', 'general'],
    icon: Calculator,
  },
  {
    id: 'support_reply',
    label: 'Répondre aux clients',
    desc: 'Emails, messages, appels entrants',
    agents: ['support', 'telephone', 'general'],
    icon: MessageSquare,
  },
  {
    id: 'content_create',
    label: 'Créer du contenu',
    desc: 'Posts réseaux, articles, newsletters',
    agents: ['content', 'video', 'general'],
    icon: FileText,
  },
  {
    id: 'lead_gen',
    label: 'Chercher des prospects',
    desc: 'Listes, qualification, relances',
    agents: ['prospector', 'closer'],
    icon: Users,
  },
  {
    id: 'reporting',
    label: 'Rapports & analyses',
    desc: 'Excel, bilans, suivi de performances',
    agents: ['analytics', 'trends', 'accounting'],
    icon: BarChart3,
  },
  {
    id: 'hiring',
    label: 'Recrutement & tri CV',
    desc: 'Annonces, screening, prise de contact',
    agents: ['recruiter', 'general'],
    icon: Search,
  },
  {
    id: 'video_prod',
    label: 'Production vidéo & visuels',
    desc: 'Montage, posts visuels, Reels',
    agents: ['video', 'content'],
    icon: Video,
  },
]

// Volume mensuel
const VOLUMES = [
  { id: 'low', label: 'Moins de 50', desc: 'clients ou prospects / mois' },
  { id: 'medium', label: 'Entre 50 et 200', desc: 'clients ou prospects / mois' },
  { id: 'high', label: 'Plus de 200', desc: 'clients ou prospects / mois' },
]

// International
const LANGUAGES = [
  { id: 'fr_only', label: 'France uniquement', desc: 'Tout en français' },
  { id: 'fr_en', label: 'Français + Anglais', desc: 'Marché francophone et international' },
  { id: 'multi', label: 'Multilingue (3+ langues)', desc: 'Europe, monde, marchés multiples' },
]

// Outils déjà utilisés (multiple)
const TOOLS_USED = [
  { id: 'crm', label: 'CRM', desc: 'HubSpot, Salesforce, Pipedrive...' },
  { id: 'compta', label: 'Compta / Facturation', desc: 'Pennylane, QuickBooks, Indy...' },
  { id: 'email_mktg', label: 'Email marketing', desc: 'Mailchimp, Brevo, Sendinblue...' },
  { id: 'ecom', label: 'Site e-commerce', desc: 'Shopify, WooCommerce, PrestaShop...' },
  { id: 'social', label: 'Réseaux sociaux', desc: 'Instagram, LinkedIn, TikTok...' },
  { id: 'support_tool', label: 'Support client', desc: 'Intercom, Crisp, Zendesk...' },
  { id: 'website', label: 'Site vitrine / blog', desc: 'WordPress, Webflow, custom...' },
  { id: 'none', label: 'Aucun outil spécifique', desc: 'On part de zéro' },
]

// ─── Helpers ─────────────────────────────────────────────────────────────────

const planLabel: Record<PlanKey, string> = { essential: 'Essentiel', pro: 'Pro' }
const planPrice: Record<PlanKey, number> = { essential: 49, pro: 79 }
const _planRank: Record<PlanKey, number> = { essential: 0, pro: 1 }

const PLAN_AGENT_LIMIT: Record<PlanKey, number> = { essential: 8, pro: 12 }

interface QuestionStep {
  title: string
  subtitle?: string
  icon: React.ComponentType<{ className?: string }>
  maxSelections?: number
}

const STEPS: QuestionStep[] = [
  { title: 'Quel est votre secteur d\'activité ?', icon: Building2 },
  { title: 'Quelle est la taille de votre structure ?', icon: Users },
  { title: 'Quels sont vos objectifs prioritaires ?', subtitle: 'Choisissez 1 à 3 objectifs', icon: Target, maxSelections: 3 },
  { title: 'Quelles tâches vous prennent le plus de temps ?', subtitle: 'Choisissez 1 à 3 réponses', icon: Clock, maxSelections: 3 },
  { title: 'Quel volume de clients ou prospects gérez-vous ?', subtitle: 'Par mois, en moyenne', icon: BarChart3 },
  { title: 'Vendez-vous à l\'international ?', icon: Globe },
  { title: 'Quels outils utilisez-vous déjà ?', subtitle: 'Plusieurs réponses possibles', icon: Wrench },
]

// ─── Scoring Engine ──────────────────────────────────────────────────────────

function computeRecommendation(params: {
  sector: string | null
  customSector: string
  size: string | null
  goals: string[]
  timeWasters: string[]
  volume: string | null
  language: string | null
  tools: string[]
}): {
  agents: AgentConfig[]
  plan: PlanKey
  scores: Record<string, number>
  integrations: string[]
} {
  const scores: Record<string, number> = {}

  const add = (agentId: string, weight: number) => {
    scores[agentId] = (scores[agentId] || 0) + weight
  }

  // Objectifs prioritaires : poids 4
  for (const goalId of params.goals) {
    const goal = GOALS.find((g) => g.id === goalId)
    if (goal) {
      for (const agentId of goal.agents) {
        add(agentId, 4)
      }
    }
  }

  // Tâches chronophages : poids 2
  for (const twId of params.timeWasters) {
    const tw = TIME_WASTERS.find((t) => t.id === twId)
    if (tw) {
      for (const agentId of tw.agents) {
        add(agentId, 2)
      }
    }
  }

  // Boost volume
  if (params.volume === 'medium') {
    add('prospector', 1)
    add('support', 1)
    add('analytics', 1)
  }
  if (params.volume === 'high') {
    add('prospector', 2)
    add('support', 2)
    add('analytics', 2)
    add('telephone', 2)
    add('closer', 2)
  }

  // Boost multilinguisme
  if (params.language === 'fr_en') {
    add('support', 2)
    add('content', 2)
    add('closer', 1)
    add('video', 1)
    add('telephone', 1)
  }
  if (params.language === 'multi') {
    add('support', 3)
    add('content', 3)
    add('closer', 2)
    add('video', 2)
    add('telephone', 2)
    add('general', 1)
  }

  // Boost structure
  if (params.size === 'small') {
    add('analytics', 1)
    add('legal', 1)
  }
  if (params.size === 'pme') {
    add('analytics', 2)
    add('legal', 2)
    add('accounting', 2)
    add('general', 1)
  }

  // Toujours un minimum pour Léo (généraliste)
  if (!scores['general']) add('general', 1)

  // Trier les agents par score décroissant
  const ranked = Object.entries(scores)
    .sort(([, a], [, b]) => b - a)
    .map(([id, score]) => ({ id, score }))

  // Calculer le plan nécessaire
  let planNeeded: PlanKey = 'essential'

  // Si des agents Pro-only sont recommandés → Pro
  const proOnlyIds = ['telephone', 'accounting', 'video', 'analytics']
  for (const { id } of ranked) {
    if (proOnlyIds.includes(id) && scores[id] >= 3) {
      planNeeded = 'pro'
      break
    }
  }

  // PME → Pro
  if (params.size === 'pme') planNeeded = 'pro'

  // Volume élevé → Pro
  if (params.volume === 'high') planNeeded = 'pro'

  // Plafond d'agents selon le plan
  const maxAgents = PLAN_AGENT_LIMIT[planNeeded]

  // Prendre les N meilleurs agents (score >= 3 minimum pour pertinence)
  const topAgentIds = ranked
    .filter((r) => r.score >= 3)
    .slice(0, maxAgents)
    .map((r) => r.id)

  // Résoudre les agents
  const agents = topAgentIds
    .map((id) => getAgentById(id))
    .filter((a): a is AgentConfig => !!a)

  // Intégrations pertinentes
  const toolToIntegrations: Record<string, string[]> = {
    crm: ['HubSpot', 'Salesforce', 'Pipedrive'],
    compta: ['Pennylane', 'QuickBooks', 'Stripe'],
    email_mktg: ['Mailchimp', 'Brevo', 'Sendinblue'],
    ecom: ['Shopify', 'WooCommerce', 'API e-commerce'],
    social: ['Buffer', 'Meta API', 'LinkedIn API'],
    support_tool: ['Intercom', 'Crisp', 'WhatsApp API'],
    website: ['WordPress', 'Webflow', 'Notion'],
    none: [],
  }

  const integrations: string[] = []
  for (const toolId of params.tools) {
    const mapped = toolToIntegrations[toolId]
    if (mapped) integrations.push(...mapped)
  }

  return {
    agents,
    plan: planNeeded,
    scores,
    integrations: [...new Set(integrations)].slice(0, 6),
  }
}

// ─── Component ───────────────────────────────────────────────────────────────

export function NeedsFinder() {
  const [step, setStep] = useState(0)
  // Q1
  const [sector, setSector] = useState<string | null>(null)
  const [customSector, setCustomSector] = useState('')
  // Q2
  const [size, setSize] = useState<string | null>(null)
  // Q3 : objectifs (max 3)
  const [goals, setGoals] = useState<string[]>([])
  // Q4 : tâches chronophages (max 3)
  const [timeWasters, setTimeWasters] = useState<string[]>([])
  // Q5 : volume
  const [volume, setVolume] = useState<string | null>(null)
  // Q6 : international
  const [language, setLanguage] = useState<string | null>(null)
  // Q7 : outils
  const [tools, setTools] = useState<string[]>([])

  const totalSteps = STEPS.length

  const toggleMulti = (
    current: string[],
    setter: React.Dispatch<React.SetStateAction<string[]>>,
    id: string,
    max: number,
  ) => {
    setter((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id)
      if (prev.length >= max) return [...prev.slice(1), id]
      return [...prev, id]
    })
  }

  const reset = () => {
    setStep(0)
    setSector(null)
    setCustomSector('')
    setSize(null)
    setGoals([])
    setTimeWasters([])
    setVolume(null)
    setLanguage(null)
    setTools([])
  }

  // Navigation guards
  const canNext = ((): boolean => {
    switch (step) {
      case 0:
        return !!sector && (sector !== 'Autre' || customSector.trim().length > 0)
      case 1:
        return !!size
      case 2:
        return goals.length > 0
      case 3:
        return timeWasters.length > 0
      case 4:
        return !!volume
      case 5:
        return !!language
      case 6:
        if (tools.length === 0 && tools.includes('none')) return true
        if (tools.length === 0) return false
        // Si "Aucun outil" est sélectionné seul, c'est OK
        if (tools.length === 1 && tools[0] === 'none') return true
        return true
      default:
        return false
    }
  })()

  const recommendation = computeRecommendation({
    sector,
    customSector,
    size,
    goals,
    timeWasters,
    volume,
    language,
    tools,
  })

  // Props pour le composant de résultat à la fin

  const isLastQuestionStep = step === totalSteps - 1

  return (
    <section id="diagnostic" className="border-t border-border py-20 md:py-28">
      <div className="container mx-auto px-4">
        {/* Header */}
        <div className="mx-auto mb-10 max-w-2xl text-center">
          <div className="mx-auto mb-4 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-sm">
            <Sparkles className="h-4 w-4 text-primary" />
            <span className="text-muted-foreground">Diagnostic gratuit · 1 minute</span>
          </div>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Quels agents IA pour <span className="gradient-text">votre activité</span>&nbsp;?
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Répondez à 7 questions, on vous recommande votre équipe d&apos;agents et la formule adaptée.
          </p>
        </div>

        <div className="mx-auto max-w-3xl rounded-2xl border border-border bg-card p-6 md:p-10">
          {step < totalSteps ? (
            <>
              {/* Barre de progression */}
              <div className="mb-8">
                <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
                  <span>
                    Question {step + 1}/{totalSteps}
                  </span>
                  <span>{Math.round(((step + 1) / totalSteps) * 100)}%</span>
                </div>
                <div className="flex items-center gap-1.5">
                  {STEPS.map((_, i) => (
                    <div
                      key={i}
                      className={`h-1.5 flex-1 rounded-full transition-all duration-300 ${
                        i < step
                          ? 'bg-primary'
                          : i === step
                            ? 'bg-primary/60'
                            : 'bg-border'
                      }`}
                    />
                  ))}
                </div>
              </div>

              {/* Titre étape */}
              <StepIcon
                Icon={STEPS[step].icon}
                title={STEPS[step].title}
                subtitle={STEPS[step].subtitle}
              />

              {/* ── Q1 : Secteur ── */}
              {step === 0 && (
                <div className="grid gap-3 sm:grid-cols-2">
                  {SECTORS.map((s) => (
                    <button
                      key={s}
                      onClick={() => setSector(s)}
                      className={`rounded-xl border p-4 text-left text-sm font-medium transition-all ${
                        sector === s
                          ? 'border-primary bg-primary/5 text-primary shadow-sm'
                          : 'border-border hover:border-primary/50 hover:bg-muted/50'
                      }`}
                    >
                      {s}
                    </button>
                  ))}
                  {sector === 'Autre' && (
                    <input
                      type="text"
                      value={customSector}
                      onChange={(e) => setCustomSector(e.target.value)}
                      placeholder="Précisez votre activité..."
                      className="col-span-full mt-1 w-full rounded-xl border border-border bg-background px-4 py-3 text-sm outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20"
                      autoFocus
                    />
                  )}
                </div>
              )}

              {/* ── Q2 : Taille ── */}
              {step === 1 && (
                <div className="grid gap-4 sm:grid-cols-3">
                  {SIZES.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => setSize(s.id)}
                      className={`rounded-xl border p-5 text-center transition-all ${
                        size === s.id
                          ? 'border-primary bg-primary/5 text-primary shadow-sm'
                          : 'border-border hover:border-primary/50 hover:bg-muted/50'
                      }`}
                    >
                      <span className="block text-sm font-semibold">{s.label}</span>
                    </button>
                  ))}
                </div>
              )}

              {/* ── Q3 : Objectifs (max 3) ── */}
              {step === 2 && (
                <div className="grid gap-3 sm:grid-cols-2">
                  {GOALS.map((g) => {
                    const active = goals.includes(g.id)
                    return (
                      <button
                        key={g.id}
                        onClick={() => toggleMulti(goals, setGoals, g.id, 3)}
                        className={`flex items-start gap-3 rounded-xl border p-4 text-left transition-all ${
                          active
                            ? 'border-primary bg-primary/5 shadow-sm'
                            : 'border-border hover:border-primary/50 hover:bg-muted/50'
                        }`}
                      >
                        <span
                          className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition-colors ${
                            active
                              ? 'border-primary bg-primary text-primary-foreground'
                              : 'border-border'
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
                  {goals.length > 0 && (
                    <p className="col-span-full text-center text-xs text-muted-foreground">
                      {goals.length}/3 objectif{goals.length > 1 ? 's' : ''} sélectionné{goals.length > 1 ? 's' : ''}
                    </p>
                  )}
                </div>
              )}

              {/* ── Q4 : Tâches chronophages (max 3) ── */}
              {step === 3 && (
                <div className="grid gap-3 sm:grid-cols-2">
                  {TIME_WASTERS.map((tw) => {
                    const active = timeWasters.includes(tw.id)
                    return (
                      <button
                        key={tw.id}
                        onClick={() => toggleMulti(timeWasters, setTimeWasters, tw.id, 3)}
                        className={`flex items-start gap-3 rounded-xl border p-4 text-left transition-all ${
                          active
                            ? 'border-primary bg-primary/5 shadow-sm'
                            : 'border-border hover:border-primary/50 hover:bg-muted/50'
                        }`}
                      >
                        <span
                          className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition-colors ${
                            active
                              ? 'border-primary bg-primary text-primary-foreground'
                              : 'border-border'
                          }`}
                        >
                          {active && <Check className="h-3.5 w-3.5" />}
                        </span>
                        <span>
                          <span className="block text-sm font-medium">{tw.label}</span>
                          <span className="block text-xs text-muted-foreground">{tw.desc}</span>
                        </span>
                      </button>
                    )
                  })}
                  {timeWasters.length > 0 && (
                    <p className="col-span-full text-center text-xs text-muted-foreground">
                      {timeWasters.length}/3 réponse{timeWasters.length > 1 ? 's' : ''} sélectionnée{timeWasters.length > 1 ? 's' : ''}
                    </p>
                  )}
                </div>
              )}

              {/* ── Q5 : Volume ── */}
              {step === 4 && (
                <div className="grid gap-4 sm:grid-cols-3">
                  {VOLUMES.map((v) => (
                    <button
                      key={v.id}
                      onClick={() => setVolume(v.id)}
                      className={`rounded-xl border p-5 text-center transition-all ${
                        volume === v.id
                          ? 'border-primary bg-primary/5 text-primary shadow-sm'
                          : 'border-border hover:border-primary/50 hover:bg-muted/50'
                      }`}
                    >
                      <span className="block text-lg font-bold">{v.label}</span>
                      <span className="block text-xs text-muted-foreground">{v.desc}</span>
                    </button>
                  ))}
                </div>
              )}

              {/* ── Q6 : International ── */}
              {step === 5 && (
                <div className="grid gap-4 sm:grid-cols-3">
                  {LANGUAGES.map((l) => (
                    <button
                      key={l.id}
                      onClick={() => setLanguage(l.id)}
                      className={`rounded-xl border p-5 text-center transition-all ${
                        language === l.id
                          ? 'border-primary bg-primary/5 text-primary shadow-sm'
                          : 'border-border hover:border-primary/50 hover:bg-muted/50'
                      }`}
                    >
                      <span className="block text-sm font-semibold">{l.label}</span>
                      <span className="block text-xs text-muted-foreground">{l.desc}</span>
                    </button>
                  ))}
                </div>
              )}

              {/* ── Q7 : Outils ── */}
              {step === 6 && (
                <>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {TOOLS_USED.map((t) => {
                      const active = tools.includes(t.id)
                      const isNone = t.id === 'none'
                      const disabledByOthers = isNone && tools.some((x) => x !== 'none')
                      const disabledByNone =
                        !isNone && tools.includes('none')

                      return (
                        <button
                          key={t.id}
                          onClick={() => {
                            if (disabledByOthers || disabledByNone) return
                            if (isNone) {
                              // Toggle : si activé, désactive ; si désactivé, vide tout et active
                              setTools((prev) =>
                                prev.includes('none') ? [] : ['none'],
                              )
                            } else {
                              setTools((prev) => {
                                const cleaned = prev.filter((x) => x !== 'none')
                                if (cleaned.includes(t.id))
                                  return cleaned.filter((x) => x !== t.id)
                                return [...cleaned, t.id]
                              })
                            }
                          }}
                          className={`flex items-start gap-3 rounded-xl border p-4 text-left transition-all ${
                            active
                              ? 'border-primary bg-primary/5 shadow-sm'
                              : disabledByNone
                                ? 'border-border opacity-40 cursor-not-allowed'
                                : 'border-border hover:border-primary/50 hover:bg-muted/50'
                          }`}
                          disabled={disabledByNone}
                        >
                          <span
                            className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition-colors ${
                              active
                                ? 'border-primary bg-primary text-primary-foreground'
                                : 'border-border'
                            }`}
                          >
                            {active && <Check className="h-3.5 w-3.5" />}
                          </span>
                          <span>
                            <span className="block text-sm font-medium">{t.label}</span>
                            <span className="block text-xs text-muted-foreground">{t.desc}</span>
                          </span>
                        </button>
                      )
                    })}
                  </div>
                  {tools.length > 0 && !tools.includes('none') && (
                    <p className="mt-3 text-center text-xs text-muted-foreground">
                      {tools.length} outil{tools.length > 1 ? 's' : ''} sélectionné{tools.length > 1 ? 's' : ''}
                      — nos agents s&apos;intègrent avec vos outils existants
                    </p>
                  )}
                </>
              )}

              {/* Navigation */}
              <div className="mt-8 flex items-center justify-between">
                <button
                  onClick={() => setStep((s) => Math.max(0, s - 1))}
                  disabled={step === 0}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-0 transition-all"
                >
                  <ArrowLeft className="h-4 w-4" /> Retour
                </button>
                <button
                  onClick={() =>
                    isLastQuestionStep
                      ? setStep((s) => s + 1) // will trigger result view
                      : setStep((s) => s + 1)
                  }
                  disabled={!canNext}
                  className="inline-flex items-center gap-2 rounded-lg bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40 transition-all shadow-sm"
                >
                  {isLastQuestionStep ? 'Voir ma recommandation' : 'Suivant'}
                  <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            </>
          ) : (
            /* ─── Résultat ─── */
            <div>
              <div className="mb-8 text-center">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10">
                  <Sparkles className="h-7 w-7 text-primary" />
                </div>
                <h3 className="text-2xl font-bold tracking-tight">
                  Votre équipe Bapica sur mesure
                </h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  Pour{' '}
                  {sector === 'Autre' && customSector.trim()
                    ? customSector.trim().toLowerCase()
                    : sector?.toLowerCase()}
                  , voici les agents qui vont transformer votre quotidien.
                </p>
              </div>

              {/* Grille d'agents recommandés */}
              {recommendation.agents.length > 0 ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  {recommendation.agents.map((agent, i) => {
                    const score = recommendation.scores[agent.id] || 0
                    const isTopPick = i === 0
                    return (
                      <div
                        key={agent.id}
                        className={`flex items-center gap-4 rounded-xl border p-4 transition-all ${
                          isTopPick
                            ? 'border-primary/40 bg-primary/5'
                            : 'border-border bg-background'
                        }`}
                      >
                        <AgentAvatar
                          agent={agent}
                          size={48}
                          className="shrink-0 rounded-xl shadow-sm"
                        />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-semibold">{agent.persona}</p>
                            {isTopPick && (
                              <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
                                Prioritaire
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground">{agent.name}</p>
                          <p className="mt-1 line-clamp-1 text-[11px] text-muted-foreground">
                            {agent.description}
                          </p>
                        </div>
                        {/* Score indicator */}
                        <div className="flex shrink-0 flex-col items-center">
                          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-xs font-bold text-muted-foreground">
                            {score}
                          </div>
                          <span className="mt-0.5 text-[9px] text-muted-foreground">
                            match
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="rounded-xl border border-border bg-muted/50 p-8 text-center">
                  <p className="text-muted-foreground">
                    Répondez à toutes les questions pour découvrir votre équipe idéale.
                  </p>
                </div>
              )}

              {/* Formule recommandée */}
              <div className="mt-8 rounded-xl border border-primary/30 bg-primary/5 p-6 text-center">
                <p className="text-sm font-medium text-muted-foreground">
                  Formule recommandée
                </p>
                <div className="mt-1 flex items-baseline justify-center gap-2">
                  <span className="text-2xl font-bold">{planLabel[recommendation.plan]}</span>
                  <span className="text-base font-normal text-muted-foreground">
                    — {planPrice[recommendation.plan]}€/mois
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  {recommendation.agents.length} agent
                  {recommendation.agents.length > 1 ? 's' : ''} recommandé
                  {recommendation.agents.length > 1 ? 's' : ''} pour votre projet
                  {recommendation.plan === 'pro' && recommendation.agents.length > 8 && (
                    <> · accès aux 12 agents</>
                  )}
                </p>

                {/* Intégrations */}
                {recommendation.integrations.length > 0 && (
                  <div className="mt-4 flex flex-wrap items-center justify-center gap-1.5">
                    <span className="text-[11px] text-muted-foreground">S&apos;intègre avec :</span>
                    {recommendation.integrations.map((name) => (
                      <span
                        key={name}
                        className="rounded-full border border-border bg-background px-2 py-0.5 text-[11px] font-medium text-foreground"
                      >
                        {name}
                      </span>
                    ))}
                  </div>
                )}

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
                    <RotateCcw className="h-4 w-4" /> Refaire le diagnostic
                  </button>
                </div>
              </div>

              {/* Résumé des réponses */}
              <details className="mt-6 rounded-xl border border-border bg-background p-4">
                <summary className="cursor-pointer text-xs font-medium text-muted-foreground hover:text-foreground transition-colors">
                  Voir le récapitulatif de vos réponses
                </summary>
                <div className="mt-3 space-y-2 text-xs text-muted-foreground">
                  <div>
                    <span className="font-medium text-foreground">Secteur :</span>{' '}
                    {sector === 'Autre' ? customSector : sector}
                  </div>
                  <div>
                    <span className="font-medium text-foreground">Taille :</span>{' '}
                    {SIZES.find((s) => s.id === size)?.label}
                  </div>
                  <div>
                    <span className="font-medium text-foreground">Objectifs :</span>{' '}
                    {goals
                      .map((gid) => GOALS.find((g) => g.id === gid)?.label)
                      .join(', ')}
                  </div>
                  <div>
                    <span className="font-medium text-foreground">Tâches chronophages :</span>{' '}
                    {timeWasters
                      .map((tid) => TIME_WASTERS.find((t) => t.id === tid)?.label)
                      .join(', ')}
                  </div>
                  <div>
                    <span className="font-medium text-foreground">Volume :</span>{' '}
                    {VOLUMES.find((v) => v.id === volume)?.label}
                  </div>
                  <div>
                    <span className="font-medium text-foreground">International :</span>{' '}
                    {LANGUAGES.find((l) => l.id === language)?.label}
                  </div>
                  <div>
                    <span className="font-medium text-foreground">Outils :</span>{' '}
                    {tools.includes('none')
                      ? 'Aucun outil'
                      : tools
                          .map((tid) => TOOLS_USED.find((t) => t.id === tid)?.label)
                          .join(', ')}
                  </div>
                </div>
              </details>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

// ─── Sub-component ───────────────────────────────────────────────────────────

function StepIcon({
  Icon,
  title,
  subtitle,
}: {
  Icon: React.ComponentType<{ className?: string }>
  title: string
  subtitle?: string
}) {
  return (
    <div className="mb-6">
      <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
        <Icon className="h-5 w-5 text-primary" />
      </div>
      <h3 className="text-xl font-semibold">{title}</h3>
      {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
    </div>
  )
}
