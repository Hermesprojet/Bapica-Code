'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { Sparkles, Loader2, Check, ArrowRight, Lock } from 'lucide-react'
import { getAgentsForPlan, type PlanKey } from '@/lib/agents'
import { getRecommendedAgentIds, type OnboardingData } from '@/lib/personalization'

// Nombre d'agents supplémentaires débloqués en passant à Pro
// (aligné avec la page facturation : Essentiel 8 → Pro 10 = Hugo + Claire).
const PRO_EXTRA_AGENTS = 2
import { CardSkeleton } from '@/components/ui/base'

// Normalise n'importe quelle valeur de plan (ex: 'Pro', 'essential', 'PRO')
// vers une clé de plan exploitable ('essential' | 'pro').
function normalizePlan(value: unknown): PlanKey {
  return String(value ?? '').toLowerCase().includes('pro') ? 'pro' : 'essential'
}

const planLabels: Record<PlanKey, string> = {
  essential: 'Essentiel',
  pro: 'Pro',
}

const agentGradients: Record<string, string> = {
  general: 'from-indigo-500 to-blue-500',
  support: 'from-emerald-500 to-green-500',
  content: 'from-indigo-500 to-blue-500',
  'prospection-strategie': 'from-emerald-500 to-teal-500',
  closer: 'from-rose-500 to-pink-500',
  telephone: 'from-cyan-500 to-teal-500',
  accounting: 'from-amber-500 to-yellow-500',
  video: 'from-pink-500 to-rose-500',
  recruiter: 'from-indigo-500 to-blue-500',
  legal: 'from-slate-500 to-gray-500',
}

export default function AgentsPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(true)
  const [recommendedIds, setRecommendedIds] = useState<string[]>([])
  const [plan, setPlan] = useState<PlanKey>('essential')

  useEffect(() => {
    supabase.auth.getUser().then(async ({ data: { user } }) => {
      if (!user) return router.push('/login')
      const onboarding: OnboardingData | null = user.user_metadata?.onboarding_data || null
      setRecommendedIds(getRecommendedAgentIds(onboarding))

      // Le plan effectif provient en priorité de profiles.plan (formule payée),
      // avec repli sur les métadonnées d'onboarding (recommended_plan).
      let resolvedPlan: PlanKey | null = null
      const { data: profile } = await supabase
        .from('profiles')
        .select('plan')
        .eq('id', user.id)
        .single()
      if (profile?.plan) {
        resolvedPlan = normalizePlan(profile.plan)
      } else {
        const metaPlan =
          user.user_metadata?.onboarding_data?.plan ??
          user.user_metadata?.recommended_plan
        if (metaPlan) resolvedPlan = normalizePlan(metaPlan)
      }
      setPlan(resolvedPlan ?? 'essential')

      setLoading(false)
    })
  }, [router])

  // N'affiche QUE les agents accessibles pour la formule de l'utilisateur.
  const availableAgents = getAgentsForPlan(plan)
  const lockedCount = PRO_EXTRA_AGENTS

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Mes agents</h1>
        <p className="mt-1 text-muted-foreground">
          {loading ? 'Chargement...' : `${recommendedIds.length} agents recommandés pour vous`}
        </p>
      </div>

      {/* Agents recommandés */}
      {!loading && recommendedIds.length > 0 && (
        <div className="mb-10">
          <h2 className="mb-4 text-sm font-semibold flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            Recommandés pour vous
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {availableAgents.filter(a => recommendedIds.includes(a.id)).map((agent) => (
              <a
                key={agent.id}
                href={`/dashboard/agents/${agent.id}`}
                className="card-elevated p-5 group relative overflow-hidden"
              >
                <div className={`absolute inset-0 bg-gradient-to-br ${agentGradients[agent.id] || 'from-primary to-primary'} opacity-0 group-hover:opacity-[0.04] transition-opacity duration-500`} />
                <div className="relative z-10">
                  <div className="flex items-center gap-3 mb-3">
                    <div className={`flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br ${agentGradients[agent.id] || 'from-primary to-primary'} text-white text-xs font-bold shadow-md`}>
                      {agent.persona.charAt(0)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-sm truncate group-hover:text-primary transition-colors">{agent.name}</h3>
                      <p className="text-xs text-muted-foreground">{agent.persona}</p>
                    </div>
                    <ArrowRight className="h-3.5 w-3.5 text-muted-foreground/60 group-hover:text-primary transition-colors" />
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
                    {agent.description}
                  </p>
                </div>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Tous les agents */}
      <div>
        <h2 className="mb-4 text-sm font-semibold">
          {!loading && recommendedIds.length > 0 ? 'Tous les agents' : 'Nos agents'}
        </h2>
        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {[1,2,3,4,5,6,7,8].map(i => <CardSkeleton key={i} />)}
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {availableAgents.map((agent) => {
              const isRecommended = recommendedIds.includes(agent.id)
              return (
                <a
                  key={agent.id}
                  href={`/dashboard/agents/${agent.id}`}
                  className={`card-elevated p-5 group relative overflow-hidden ${
                    isRecommended ? 'ring-1 ring-primary/20' : ''
                  }`}
                >
                  {isRecommended && (
                    <div className="absolute top-3 right-3 z-10">
                      <Check className="h-3.5 w-3.5 text-primary" />
                    </div>
                  )}
                  <div className={`absolute inset-0 bg-gradient-to-br ${agentGradients[agent.id] || 'from-primary to-primary'} opacity-0 group-hover:opacity-[0.04] transition-opacity duration-500`} />
                  <div className="relative z-10">
                    <div className="flex items-center gap-3 mb-3">
                      <div className={`flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br ${agentGradients[agent.id] || 'from-primary to-primary'} text-white text-xs font-bold shadow-md`}>
                        {agent.persona.charAt(0)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="font-semibold text-sm truncate group-hover:text-primary transition-colors">{agent.name}</h3>
                        <p className="text-xs text-muted-foreground">{agent.persona}</p>
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2 mb-3">
                      {agent.description}
                    </p>
                    <div className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${
                      agent.minPlan === 'essential'
                        ? 'bg-indigo-500/10 text-indigo-400'
                        : 'bg-blue-500/10 text-blue-400'
                    }`}>
                      {planLabels[agent.minPlan]}
                    </div>
                    {isRecommended && (
                      <span className="ml-1.5 inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium bg-primary/10 text-primary">
                        ★ Conseillé
                      </span>
                    )}
                  </div>
                </a>
              )
            })}
          </div>
        )}

        {/* Invitation à passer au plan Pro pour débloquer les agents avancés */}
        {!loading && plan === 'essential' && lockedCount > 0 && (
          <a
            href="/dashboard/billing"
            className="mt-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 rounded-xl border border-primary/30 bg-gradient-to-br from-primary/10 to-purple-500/5 p-5 group transition-colors hover:border-primary/50"
          >
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/15 text-primary">
                <Lock className="h-4 w-4" />
              </div>
              <div>
                <h3 className="font-semibold text-sm">
                  Passez au plan Pro pour débloquer les {lockedCount} agents supplémentaires
                </h3>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Standard téléphonique 24/7 (Hugo) et comptabilité (Claire).
                </p>
              </div>
            </div>
            <span className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground group-hover:opacity-90 transition-opacity">
              Passer à Pro
              <ArrowRight className="h-3.5 w-3.5" />
            </span>
          </a>
        )}
      </div>
    </div>
  )
}
