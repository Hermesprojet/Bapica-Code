'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { Bot, Users, MessageSquare, TrendingUp, Loader2, ArrowRight, Sparkles } from 'lucide-react'
import { getSetupSteps, getRecommendedWidgets, getRecommendedAgentIds, type OnboardingData } from '@/lib/personalization'
import { DashboardSkeleton } from '@/components/ui/base'

export default function DashboardPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(true)
  const [onboarding, setOnboarding] = useState<OnboardingData | null>(null)

  useEffect(() => {
    supabase.auth.getUser().then(async ({ data: { user } }) => {
      if (!user) {
        router.push('/login')
        return
      }

      // Vérifier onboarding + récupérer données
      const onboarded = user.user_metadata?.onboarding_completed
      if (!onboarded) {
        router.push('/onboarding')
        return
      }

      setOnboarding(user.user_metadata?.onboarding_data || null)
      setLoading(false)
    })
  }, [router])

  if (loading) return <DashboardSkeleton />

  const steps = getSetupSteps(onboarding)
  const widgets = getRecommendedWidgets(onboarding)
  const doneSteps = steps.filter(s => s.done).length
  const progressPct = Math.round((doneSteps / steps.length) * 100)
  const allDone = progressPct >= 100

  return (
    <div>
      {/* En-tête */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Tableau de bord</h1>
        <p className="mt-1 text-muted-foreground">
          Bienvenue sur votre espace Bapica.
        </p>
      </div>

      {/* Barre de progression configuration */}
      {!allDone && steps.length > 1 && (
        <div className="card-elevated mb-8 p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              <h3 className="font-semibold text-sm">Finalisez votre configuration</h3>
            </div>
            <span className="text-xs text-muted-foreground">{doneSteps}/{steps.length}</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/5">
            <div
              className="h-full rounded-full bg-gradient-to-r from-primary to-purple-500 transition-all duration-700 ease-out"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <div className="mt-4 space-y-2">
            {steps.filter(s => !s.done).slice(0, 3).map(s => (
              <a
                key={s.key}
                href={s.href}
                className="group flex items-center gap-3 rounded-lg px-3 py-2 text-sm hover:bg-white/5 transition-colors"
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-full border border-white/10 text-[10px] text-muted-foreground">
                  {steps.indexOf(s) + 1}
                </span>
                <span className="flex-1">{s.label}</span>
                <ArrowRight className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Cartes stats */}
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { icon: Bot, title: 'Agents actifs', value: '12', desc: 'disponibles', change: '+2 ce mois' },
          { icon: MessageSquare, title: 'Conversations', value: '0', desc: 'ce mois-ci', change: 'À venir' },
          { icon: Users, title: 'Leads générés', value: '0', desc: "par vos agents", change: 'Bientôt' },
          { icon: TrendingUp, title: 'Crédits', value: '∞', desc: 'messages illimités', change: 'Illimité' },
        ].map((card) => {
          const Icon = card.icon
          return (
            <div key={card.title} className="card-elevated p-5">
              <div className="flex items-center justify-between">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Icon className="h-4.5 w-4.5" />
                </div>
                <span className="text-[11px] font-medium text-green-400">
                  {card.change}
                </span>
              </div>
              <div className="mt-4">
                <p className="text-2xl font-bold">{card.value}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{card.title}</p>
                <p className="text-[11px] text-muted-foreground">{card.desc}</p>
              </div>
            </div>
          )
        })}
      </div>

      {/* Widgets intelligents personnalisés */}
      {widgets.length > 0 && (
        <div className="mt-10">
          <h2 className="mb-4 text-sm font-semibold flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            Recommandé pour vous
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {widgets.slice(0, 4).map(w => (
              <a
                key={w.id}
                href={w.href}
                className="card-elevated p-5 flex items-start justify-between gap-4 group"
              >
                <div className="flex-1">
                  <h3 className="font-semibold text-sm group-hover:text-primary transition-colors">
                    {w.title}
                  </h3>
                  <p className="mt-1.5 text-xs text-muted-foreground leading-relaxed">
                    {w.description}
                  </p>
                </div>
                <span className="shrink-0 rounded-lg border border-white/10 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/10 transition-colors">
                  {w.cta}
                </span>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Actions rapides */}
      <div className="mt-10">
        <h2 className="mb-4 text-sm font-semibold">Actions rapides</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[
            { href: '/dashboard/agents', title: '🤖 Parler à un agent', desc: 'Discutez avec vos assistants IA spécialisés.' },
            { href: '/dashboard/billing', title: '📊 Gérer mon abonnement', desc: 'Voir votre forfait, changer de formule.' },
            { href: '/dashboard/settings', title: '⚙️ Configuration', desc: 'API keys, préférences, connexions.' },
          ].map(item => (
            <a
              key={item.href}
              href={item.href}
              className="card-elevated p-5 group"
            >
              <h3 className="font-semibold text-sm group-hover:text-primary transition-colors">{item.title}</h3>
              <p className="mt-2 text-xs text-muted-foreground leading-relaxed">{item.desc}</p>
            </a>
          ))}
        </div>
      </div>
    </div>
  )
}
