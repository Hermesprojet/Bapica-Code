'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { Loader2, Check, ArrowRight, ArrowLeft, Bot, FileText, Phone, Globe, Zap, Shield, Plus, X, Sparkles } from 'lucide-react'
import Link from 'next/link'

type Activity = 'independant' | 'tpe' | 'pme' | 'ecommerce' | 'service' | 'autre'

const activities = [
  { id: 'independant' as Activity, label: 'Indépendant / Freelance', icon: '👤' },
  { id: 'tpe' as Activity, label: 'TPE (moins de 10 salariés)', icon: '🏪' },
  { id: 'pme' as Activity, label: 'PME (10-50 salariés)', icon: '🏢' },
  { id: 'ecommerce' as Activity, label: 'E-commerce', icon: '🛒' },
  { id: 'service' as Activity, label: 'Prestataire de services', icon: '🔧' },
  { id: 'autre' as Activity, label: 'Autre', icon: '📋' },
]

const adminTasks = [
  { id: 'factures', label: 'Gestion des factures et devis', icon: '📄' },
  { id: 'comptabilite', label: 'Comptabilité / TVA', icon: '🧮' },
  { id: 'juridique', label: 'Documents juridiques (CGV, contrats)', icon: '⚖️' },
  { id: 'paie', label: 'Paie et RH', icon: '👥' },
  { id: 'planning', label: 'Planning et rendez-vous', icon: '📅' },
  { id: 'notes', label: 'Notes de frais', icon: '💰' },
  { id: 'autre', label: 'Autre (précisez)', icon: '✏️' },
]

const contactMethods = [
  { id: 'telephone', label: 'Téléphone (appels entrants)', icon: '📞' },
  { id: 'whatsapp', label: 'WhatsApp', icon: '💬' },
  { id: 'email', label: 'Email', icon: '📧' },
  { id: 'linkedin', label: 'LinkedIn', icon: '🔗' },
  { id: 'chat', label: 'Chat sur site web', icon: '💻' },
  { id: 'sms', label: 'SMS', icon: '✉️' },
  { id: 'autre', label: 'Autre (précisez)', icon: '✏️' },
]

const objectives = [
  { id: 'ventes', label: 'Augmenter mes ventes / prospects', icon: '📈' },
  { id: 'support', label: 'Améliorer mon support client', icon: '🎧' },
  { id: 'compta', label: 'Automatiser la compta / admin', icon: '🧮' },
  { id: 'contenu', label: 'Créer du contenu plus vite', icon: '✍️' },
  { id: 'presence', label: 'Améliorer ma présence en ligne', icon: '🌐' },
  { id: 'recrutement', label: 'Recruter plus efficacement', icon: '👔' },
  { id: 'autre', label: 'Autre (précisez)', icon: '✏️' },
]

interface ConnectedApp {
  name: string
  url?: string
}

interface OnboardingData {
  activity: string
  activityOther: string
  adminTasks: string[]
  adminTasksOther: string
  contactMethods: string[]
  contactMethodsOther: string
  apps: ConnectedApp[]
  appsOther: string
  businessDescription: string
  objectives: string[]
  objectivesOther: string
}

interface AgentSuggestion {
  id: string
  name: string
  description: string
  icon: string
}

// Analyse la description + objectifs et recommande des agents
function suggestAgents(data: OnboardingData): AgentSuggestion[] {
  const text = `${data.businessDescription} ${data.objectives.join(' ')}`.toLowerCase()
  const suggestions: AgentSuggestion[] = []
  const has = (...keywords: string[]) => keywords.some((k) => text.includes(k))

  if (has('prospect', 'vente', 'lead', 'ventes')) {
    suggestions.push({
      id: 'prospecteur',
      name: 'Prospecteur Commercial',
      description: 'Identifie et contacte automatiquement vos prospects qualifiés.',
      icon: '🎯',
    })
  }
  if (has('support', 'client', 'service')) {
    suggestions.push({
      id: 'support',
      name: 'Support Client',
      description: 'Répond à vos clients 24/7 et résout leurs demandes courantes.',
      icon: '🎧',
    })
  }
  if (has('compta', 'facture', 'comptabilité', 'comptabilite')) {
    suggestions.push({
      id: 'comptabilite',
      name: 'Agent Comptabilité',
      description: 'Gère vos factures, devis et le suivi de votre comptabilité.',
      icon: '🧮',
    })
  }
  if (has('contenu', 'réseaux', 'reseaux', 'instagram', 'linkedin')) {
    suggestions.push({
      id: 'contenu',
      name: 'Créateur de Contenu',
      description: 'Produit des posts, articles et visuels pour vos réseaux.',
      icon: '✍️',
    })
  }
  if (has('recrute', 'embauche', 'cv')) {
    suggestions.push({
      id: 'recruteur',
      name: 'Recruteur IA',
      description: 'Trie les candidatures et présélectionne les meilleurs profils.',
      icon: '👔',
    })
  }

  if (suggestions.length === 0) {
    suggestions.push({
      id: 'general',
      name: 'Agent Général',
      description: 'Un assistant polyvalent pour vous épauler au quotidien.',
      icon: '🤖',
    })
  }

  return suggestions
}

function recommendPlan(data: OnboardingData) {
  const appsText = data.apps.map((a) => a.name.toLowerCase()).join(' ')
  const needsPhone = data.contactMethods.includes('telephone')
  const needsAdvanced = data.adminTasks.includes('juridique') || data.adminTasks.includes('paie')
  const needsEcommerce = data.activity === 'ecommerce' || appsText.includes('shopify')
  const score = (needsPhone ? 2 : 0) + (needsAdvanced ? 2 : 0) + (needsEcommerce ? 1 : 0) + (data.apps.length >= 3 ? 1 : 0)

  return {
    plan: score >= 3 ? 'Pro' : 'Essentiel',
    price: score >= 3 ? '79€' : '49€',
    agents: score >= 3 
      ? ['Agent Téléphonique', 'Agent Juridique', 'Agent Comptable', 'Prospecteur', 'Assistant Général']
      : ['Assistant Général', 'Support Client', 'Créateur de Contenu', 'Agent SEO'],
  }
}

export default function OnboardingPage() {
  const router = useRouter()
  const [step, setStep] = useState(0)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [user, setUser] = useState<any>(null)

  const [data, setData] = useState<OnboardingData>({
    activity: '',
    activityOther: '',
    adminTasks: [],
    adminTasksOther: '',
    contactMethods: [],
    contactMethodsOther: '',
    apps: [],
    appsOther: '',
    businessDescription: '',
    objectives: [],
    objectivesOther: '',
  })

  // Champs temporaires pour l'ajout dynamique d'applications
  const [newAppName, setNewAppName] = useState('')
  const [newAppUrl, setNewAppUrl] = useState('')

  const addApp = () => {
    const name = newAppName.trim()
    if (!name) return
    const url = newAppUrl.trim()
    setData((prev) => ({
      ...prev,
      apps: [...prev.apps, { name, ...(url ? { url } : {}) }],
    }))
    setNewAppName('')
    setNewAppUrl('')
  }

  const removeApp = (index: number) => {
    setData((prev) => ({
      ...prev,
      apps: prev.apps.filter((_, i) => i !== index),
    }))
  }

  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => {
      if (!user) {
        router.push('/login')
        return
      }
      setUser(user)
      // Vérifier si l'onboarding est déjà complété
      supabase.from('profiles').select('onboarding_completed').eq('id', user.id).single().then(({ data: profile }) => {
        if (profile?.onboarding_completed) {
          router.push('/dashboard')
          return
        }
        setLoading(false)
      })
    })
  }, [router])

  const toggleItem = (key: keyof OnboardingData, id: string) => {
    setData((prev: OnboardingData) => {
      const arr = prev[key] as unknown as string[]
      if (arr.includes(id)) {
        return { ...prev, [key]: arr.filter((i: string) => i !== id) }
      }
      return { ...prev, [key]: [...arr, id] }
    })
  }

  const handleSubmit = async () => {
    if (!user) return
    setSaving(true)

    const recommendation = recommendPlan(data)
    const recommendedAgents = suggestAgents(data)

    // Sauvegarder dans user_metadata (pas besoin de modifier le schéma)
    await supabase.auth.updateUser({
      data: {
        onboarding_completed: true,
        onboarding_data: data,
        recommended_plan: recommendation.plan,
        recommended_agents: recommendedAgents.map((a) => a.name),
        company_activity: data.activity,
      }
    })

    // Essayer aussi de sauvegarder dans profiles (si les colonnes existent)
    try {
      await supabase.from('profiles').update({
        onboarding_completed: true,
        recommended_plan: recommendation.plan,
      }).eq('id', user.id)
    } catch (e) {
      // Les colonnes n'existent pas encore, ce n'est pas bloquant
    }

    setSaving(false)
    router.push('/dashboard')
  }

  const canContinue = () => {
    switch (step) {
      case 0: return data.activity !== ''
      case 1: return data.adminTasks.length > 0
      case 2: return data.contactMethods.length > 0
      case 3: return true
      case 4: return data.businessDescription.trim().length > 0
      default: return true
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  const recommendation = step === 5 ? recommendPlan(data) : null
  const agentSuggestions = step === 5 ? suggestAgents(data) : []
  const totalSteps = 6

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-primary/[0.02]">
      {/* Header */}
      <div className="border-b border-border bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <Link href="/" className="text-lg font-bold">
            <span className="gradient-text">Bapica</span>
          </Link>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="font-medium text-foreground">Étape {step + 1}</span>
            <span>/ {totalSteps}</span>
          </div>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-muted">
        <div
          className="h-full bg-gradient-to-r from-primary to-purple-500 transition-all duration-500 ease-out"
          style={{ width: `${((step + 1) / totalSteps) * 100}%` }}
        />
      </div>

      <div className="container mx-auto max-w-2xl px-4 py-12">
        {/* Step 0: Activité */}
        {step === 0 && (
          <div className="animate-slide-up">
            <div className="text-center mb-8">
              <div className="inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-primary/10 text-3xl mb-4">
                🏢
              </div>
              <h1 className="text-2xl font-bold">Parlez-nous de votre activité</h1>
              <p className="mt-2 text-muted-foreground">
                Cela nous aide à personnaliser votre expérience Bapica.
              </p>
            </div>
            <div className="grid gap-3">
              {activities.map((a) => (
                <button
                  key={a.id}
                  onClick={() => setData(prev => ({ ...prev, activity: a.id }))}
                  className={`flex items-center gap-4 rounded-xl border p-4 text-left transition-all ${
                    data.activity === a.id
                      ? 'border-primary bg-primary/5 shadow-md'
                      : 'border-border bg-card hover:border-primary/30'
                  }`}
                >
                  <span className="text-2xl">{a.icon}</span>
                  <span className="font-medium">{a.label}</span>
                  {data.activity === a.id && (
                    <Check className="ml-auto h-5 w-5 text-primary" />
                  )}
                </button>
              ))}
            </div>
            {data.activity === 'autre' && (
              <div className="mt-4 animate-slide-up">
                <label htmlFor="activity-other" className="mb-1.5 block text-sm font-medium">
                  Précisez votre activité
                </label>
                <input
                  id="activity-other"
                  type="text"
                  autoFocus
                  value={data.activityOther}
                  onChange={(e) => setData(prev => ({ ...prev, activityOther: e.target.value }))}
                  placeholder="Ex : Association, profession libérale, artisan…"
                  className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            )}
          </div>
        )}

        {/* Step 1: Tâches administratives */}
        {step === 1 && (
          <div className="animate-slide-up">
            <div className="text-center mb-8">
              <div className="inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-primary/10 text-3xl mb-4">
                📋
              </div>
              <h1 className="text-2xl font-bold">Quelles tâches administratives vous prennent du temps ?</h1>
              <p className="mt-2 text-muted-foreground">
                Choisissez celles que vous aimeriez automatiser.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {adminTasks.map((t) => (
                <button
                  key={t.id}
                  onClick={() => toggleItem('adminTasks', t.id)}
                  className={`flex items-center gap-3 rounded-xl border p-4 text-left transition-all ${
                    data.adminTasks.includes(t.id)
                      ? 'border-primary bg-primary/5 shadow-md'
                      : 'border-border bg-card hover:border-primary/30'
                  }`}
                >
                  <span className="text-xl">{t.icon}</span>
                  <span className="text-sm font-medium">{t.label}</span>
                  {data.adminTasks.includes(t.id) && (
                    <Check className="ml-auto h-4 w-4 text-primary shrink-0" />
                  )}
                </button>
              ))}
            </div>
            {data.adminTasks.includes('autre') && (
              <div className="mt-4 animate-slide-up">
                <label htmlFor="admin-other" className="mb-1.5 block text-sm font-medium">
                  Précisez la ou les tâches
                </label>
                <input
                  id="admin-other"
                  type="text"
                  autoFocus
                  value={data.adminTasksOther}
                  onChange={(e) => setData(prev => ({ ...prev, adminTasksOther: e.target.value }))}
                  placeholder="Ex : relances clients, gestion des stocks…"
                  className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            )}
          </div>
        )}

        {/* Step 2: Contact clients */}
        {step === 2 && (
          <div className="animate-slide-up">
            <div className="text-center mb-8">
              <div className="inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-primary/10 text-3xl mb-4">
                📞
              </div>
              <h1 className="text-2xl font-bold">Comment vos clients vous contactent-ils ?</h1>
              <p className="mt-2 text-muted-foreground">
                Sélectionnez tous les canaux que vous utilisez.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {contactMethods.map((m) => (
                <button
                  key={m.id}
                  onClick={() => toggleItem('contactMethods', m.id)}
                  className={`flex items-center gap-3 rounded-xl border p-4 text-left transition-all ${
                    data.contactMethods.includes(m.id)
                      ? 'border-primary bg-primary/5 shadow-md'
                      : 'border-border bg-card hover:border-primary/30'
                  }`}
                >
                  <span className="text-xl">{m.icon}</span>
                  <span className="text-sm font-medium">{m.label}</span>
                  {data.contactMethods.includes(m.id) && (
                    <Check className="ml-auto h-4 w-4 text-primary shrink-0" />
                  )}
                </button>
              ))}
            </div>
            {data.contactMethods.includes('autre') && (
              <div className="mt-4 animate-slide-up">
                <label htmlFor="contact-other" className="mb-1.5 block text-sm font-medium">
                  Précisez le canal
                </label>
                <input
                  id="contact-other"
                  type="text"
                  autoFocus
                  value={data.contactMethodsOther}
                  onChange={(e) => setData(prev => ({ ...prev, contactMethodsOther: e.target.value }))}
                  placeholder="Ex : Messenger, Instagram, formulaire de contact…"
                  className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            )}
          </div>
        )}

        {/* Step 3: Apps à connecter (champ libre) */}
        {step === 3 && (
          <div className="animate-slide-up">
            <div className="text-center mb-8">
              <div className="inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-primary/10 text-3xl mb-4">
                🔌
              </div>
              <h1 className="text-2xl font-bold">Quelles applications souhaitez-vous connecter ?</h1>
              <p className="mt-2 text-muted-foreground">
                Ajoutez vos outils un par un. Bapica se connectera à vos applications existantes.
              </p>
            </div>

            {/* Formulaire d'ajout */}
            <div className="rounded-xl border border-border bg-card p-4 sm:p-5">
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label htmlFor="app-name" className="mb-1.5 block text-sm font-medium text-foreground">
                    Nom de l&apos;application <span className="text-primary">*</span>
                  </label>
                  <input
                    id="app-name"
                    type="text"
                    value={newAppName}
                    onChange={(e) => setNewAppName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        addApp()
                      }
                    }}
                    placeholder="Ex : Shopify, Notion, Qonto…"
                    className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
                <div>
                  <label htmlFor="app-url" className="mb-1.5 block text-sm font-medium text-foreground">
                    URL ou site web <span className="text-muted-foreground">(optionnel)</span>
                  </label>
                  <input
                    id="app-url"
                    type="url"
                    value={newAppUrl}
                    onChange={(e) => setNewAppUrl(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        addApp()
                      }
                    }}
                    placeholder="https://exemple.com"
                    className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              </div>
              <button
                type="button"
                onClick={addApp}
                disabled={!newAppName.trim()}
                className="mt-3 flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-all"
              >
                <Plus className="h-4 w-4" />
                Ajouter
              </button>
            </div>

            {/* Liste des apps ajoutées */}
            {data.apps.length > 0 && (
              <div className="mt-5 animate-slide-up">
                <p className="mb-3 text-sm font-medium text-muted-foreground">
                  Applications ajoutées ({data.apps.length})
                </p>
                <div className="flex flex-wrap gap-2">
                  {data.apps.map((app, index) => (
                    <span
                      key={`${app.name}-${index}`}
                      className="inline-flex items-center gap-2 rounded-full border border-primary/40 bg-primary/10 py-1.5 pl-3 pr-1.5 text-sm text-foreground"
                    >
                      <span className="font-medium">{app.name}</span>
                      {app.url && (
                        <a
                          href={app.url.startsWith('http') ? app.url : `https://${app.url}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                        >
                          <Globe className="h-3 w-3" />
                          Lien
                        </a>
                      )}
                      <button
                        type="button"
                        onClick={() => removeApp(index)}
                        aria-label={`Supprimer ${app.name}`}
                        className="inline-flex h-6 w-6 items-center justify-center rounded-full text-muted-foreground hover:bg-primary/20 hover:text-foreground transition-colors"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Autre (précisez) */}
            <div className="mt-6">
              <label htmlFor="apps-other" className="mb-1.5 block text-sm font-medium text-foreground">
                Autre (précisez)
              </label>
              <input
                id="apps-other"
                type="text"
                value={data.appsOther}
                onChange={(e) => setData(prev => ({ ...prev, appsOther: e.target.value }))}
                placeholder="Un outil interne, une API spécifique, un besoin particulier…"
                className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <p className="mt-1.5 text-xs text-muted-foreground">
                Dites-nous ce que vous utilisez, nous étudierons la connexion.
              </p>
            </div>
          </div>
        )}

        {/* Step 4: Analyse de vos besoins */}
        {step === 4 && (
          <div className="animate-slide-up">
            <div className="text-center mb-8">
              <div className="inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-primary/10 text-3xl mb-4">
                💡
              </div>
              <h1 className="text-2xl font-bold">Parlez-nous de votre activité</h1>
              <p className="mt-2 text-muted-foreground">
                Plus vous êtes précis, mieux nous recommandons les bons agents.
              </p>
            </div>

            <div>
              <label htmlFor="business-description" className="mb-1.5 block text-sm font-medium text-foreground">
                Décrivez votre activité et vos besoins <span className="text-primary">*</span>
              </label>
              <textarea
                id="business-description"
                rows={6}
                value={data.businessDescription}
                onChange={(e) => setData(prev => ({ ...prev, businessDescription: e.target.value }))}
                placeholder="Ex: Je gère une petite agence de communication de 5 personnes. Nous avons besoin d'automatiser la prospection sur LinkedIn, la création de contenu pour nos clients, et la facturation. Nous utilisons actuellement Notion et Google Sheets."
                className="w-full resize-none rounded-xl border border-border bg-background px-4 py-3 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <div className="mt-8">
              <h2 className="mb-1 text-lg font-semibold text-foreground">Vos objectifs principaux</h2>
              <p className="mb-4 text-sm text-muted-foreground">
                Sélectionnez tout ce qui correspond à vos priorités.
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                {objectives.map((o) => (
                  <button
                    key={o.id}
                    onClick={() => toggleItem('objectives', o.id)}
                    className={`flex items-center gap-3 rounded-xl border p-4 text-left transition-all ${
                      data.objectives.includes(o.id)
                        ? 'border-primary bg-primary/5 shadow-md'
                        : 'border-border bg-card hover:border-primary/30'
                    }`}
                  >
                    <span className="text-xl">{o.icon}</span>
                    <span className="text-sm font-medium text-foreground">{o.label}</span>
                    {data.objectives.includes(o.id) && (
                      <Check className="ml-auto h-4 w-4 text-primary shrink-0" />
                    )}
                  </button>
                ))}
              </div>
              {data.objectives.includes('autre') && (
                <div className="mt-4 animate-slide-up">
                  <label htmlFor="objectives-other" className="mb-1.5 block text-sm font-medium text-foreground">
                    Précisez votre objectif
                  </label>
                  <input
                    id="objectives-other"
                    type="text"
                    autoFocus
                    value={data.objectivesOther}
                    onChange={(e) => setData(prev => ({ ...prev, objectivesOther: e.target.value }))}
                    placeholder="Ex : fidéliser mes clients, gagner du temps sur le reporting…"
                    className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {/* Step 5: Recommandation */}
        {step === 5 && recommendation && (
          <div className="animate-slide-up text-center">
            <div className="inline-flex items-center justify-center h-20 w-20 rounded-full bg-gradient-to-br from-primary to-purple-500 text-4xl mb-6 shadow-lg shadow-primary/25">
              🎯
            </div>
            <h1 className="text-2xl font-bold">Voici la formule idéale pour vous</h1>
            <p className="mt-2 text-muted-foreground mb-8">
              Basé sur vos réponses, nous vous recommandons :
            </p>

            <div className="mx-auto max-w-sm rounded-2xl border-2 border-primary bg-card p-8 shadow-xl shadow-primary/10">
              <p className="text-sm font-medium text-primary mb-1">Recommandé pour vous</p>
              <h2 className="text-3xl font-bold">{recommendation.plan}</h2>
              <p className="mt-2 text-2xl font-bold">
                {recommendation.price}
                <span className="text-sm font-normal text-muted-foreground">/mois</span>
              </p>

              <div className="mt-6 space-y-3 text-left">
                <p className="text-sm font-medium text-muted-foreground">Agents inclus :</p>
                {recommendation.agents.map((agent) => (
                  <div key={agent} className="flex items-center gap-3 text-sm">
                    <Check className="h-4 w-4 text-green-500 shrink-0" />
                    <span>{agent}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Nos recommandations d'agents basées sur l'analyse */}
            <div className="mt-10 text-left animate-slide-up">
              <div className="mb-4 flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" />
                <h2 className="text-xl font-bold text-foreground">Nos recommandations</h2>
              </div>
              <p className="mb-5 text-sm text-muted-foreground">
                D&apos;après votre description, ces agents sont les plus adaptés à vos besoins :
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                {agentSuggestions.map((agent) => (
                  <div
                    key={agent.id}
                    className="relative flex items-start gap-4 rounded-xl border border-primary/40 bg-primary/5 p-4"
                  >
                    <span className="absolute right-3 top-3 inline-flex items-center gap-1 rounded-full bg-gradient-to-r from-primary to-purple-500 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-primary-foreground shadow-sm">
                      <Sparkles className="h-3 w-3" />
                      Recommandé
                    </span>
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-2xl">
                      {agent.icon}
                    </span>
                    <div className="pr-16">
                      <h3 className="font-semibold text-foreground">{agent.name}</h3>
                      <p className="mt-0.5 text-sm text-muted-foreground">{agent.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-8 rounded-xl border border-border bg-card/50 p-4 text-sm text-muted-foreground text-left">
              <p className="font-medium text-foreground mb-1">🔧 Prochaine étape</p>
              <p>Après votre inscription, nous vous demanderons l&apos;accès à vos outils pour configurer vos agents.</p>
            </div>
          </div>
        )}

        {/* Navigation buttons */}
        <div className="mt-10 flex items-center justify-between">
          <button
            onClick={() => setStep(Math.max(0, step - 1))}
            className={`flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-all ${
              step === 0 ? 'invisible' : 'hover:bg-muted'
            }`}
          >
            <ArrowLeft className="h-4 w-4" />
            Retour
          </button>

          {step < 5 ? (
            <button
              onClick={() => setStep(step + 1)}
              disabled={!canContinue()}
              className="flex items-center gap-2 rounded-lg bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-all"
            >
              Suivant
              <ArrowRight className="h-4 w-4" />
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={saving}
              className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-primary to-purple-500 px-6 py-2.5 text-sm font-medium text-primary-foreground shadow-lg hover:shadow-xl transition-all disabled:opacity-50"
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  Accéder à mon espace
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
