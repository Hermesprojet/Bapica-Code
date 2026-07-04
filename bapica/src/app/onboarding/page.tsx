'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { Loader2, Check, ArrowRight, ArrowLeft, Bot, FileText, Phone, Globe, Zap, Shield } from 'lucide-react'
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
]

const contactMethods = [
  { id: 'telephone', label: 'Téléphone (appels entrants)', icon: '📞' },
  { id: 'whatsapp', label: 'WhatsApp', icon: '💬' },
  { id: 'email', label: 'Email', icon: '📧' },
  { id: 'linkedin', label: 'LinkedIn', icon: '🔗' },
  { id: 'chat', label: 'Chat sur site web', icon: '💻' },
  { id: 'sms', label: 'SMS', icon: '✉️' },
]

const integrations = [
  { id: 'google', label: 'Google Agenda / Workspace', icon: '📅' },
  { id: 'notion', label: 'Notion', icon: '📝' },
  { id: 'slack', label: 'Slack', icon: '💬' },
  { id: 'hubspot', label: 'HubSpot', icon: '📊' },
  { id: 'wordpress', label: 'WordPress', icon: '🌐' },
  { id: 'shopify', label: 'Shopify', icon: '🛍️' },
  { id: 'stripe', label: 'Stripe', icon: '💳' },
  { id: 'qonto', label: 'Qonto', icon: '🏦' },
]

interface OnboardingData {
  activity: string
  adminTasks: string[]
  contactMethods: string[]
  integrations: string[]
}

function recommendPlan(data: OnboardingData) {
  const needsPhone = data.contactMethods.includes('telephone')
  const needsAdvanced = data.adminTasks.includes('juridique') || data.adminTasks.includes('paie')
  const needsEcommerce = data.activity === 'ecommerce' || data.integrations.includes('shopify')
  const score = (needsPhone ? 2 : 0) + (needsAdvanced ? 2 : 0) + (needsEcommerce ? 1 : 0) + (data.integrations.length >= 3 ? 1 : 0)

  return {
    plan: score >= 3 ? 'Pro' : 'Essentiel',
    price: score >= 3 ? '79€' : '39€',
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
    adminTasks: [],
    contactMethods: [],
    integrations: [],
  })

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

    // Sauvegarder dans user_metadata (pas besoin de modifier le schéma)
    await supabase.auth.updateUser({
      data: {
        onboarding_completed: true,
        onboarding_data: data,
        recommended_plan: recommendation.plan,
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

  const recommendation = step === 4 ? recommendPlan(data) : null
  const totalSteps = 5

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
          </div>
        )}

        {/* Step 3: Intégrations */}
        {step === 3 && (
          <div className="animate-slide-up">
            <div className="text-center mb-8">
              <div className="inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-primary/10 text-3xl mb-4">
                🔌
              </div>
              <h1 className="text-2xl font-bold">Quels outils utilisez-vous ?</h1>
              <p className="mt-2 text-muted-foreground">
                Bapica se connecte à vos applications existantes.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {integrations.map((i) => (
                <button
                  key={i.id}
                  onClick={() => toggleItem('integrations', i.id)}
                  className={`flex items-center gap-3 rounded-xl border p-4 text-left transition-all ${
                    data.integrations.includes(i.id)
                      ? 'border-primary bg-primary/5 shadow-md'
                      : 'border-border bg-card hover:border-primary/30'
                  }`}
                >
                  <span className="text-xl">{i.icon}</span>
                  <span className="text-sm font-medium">{i.label}</span>
                  {data.integrations.includes(i.id) && (
                    <Check className="ml-auto h-4 w-4 text-primary shrink-0" />
                  )}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 4: Recommandation */}
        {step === 4 && recommendation && (
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

            <div className="mt-8 rounded-xl border border-border bg-card/50 p-4 text-sm text-muted-foreground">
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

          {step < 4 ? (
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
