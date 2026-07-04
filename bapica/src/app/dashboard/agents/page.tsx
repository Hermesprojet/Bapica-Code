'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { Sparkles, Loader2, Check, ArrowRight } from 'lucide-react'
import AGENTS, { type PlanKey } from '@/lib/agents'
import { AgentAvatar } from '@/components/agents/agent-avatar'
import { getRecommendedAgentIds, type OnboardingData } from '@/lib/personalization'
import { CardSkeleton } from '@/components/ui/base'

const planLabels: Record<PlanKey, string> = {
  essential: 'Essentiel',
  pro: 'Pro',
}

const agentGradients: Record<string, string> = {
  general: 'from-violet-500 to-purple-500',
  support: 'from-emerald-500 to-green-500',
  content: 'from-violet-500 to-purple-500',
  prospector: 'from-orange-500 to-amber-500',
  closer: 'from-rose-500 to-pink-500',
  telephone: 'from-cyan-500 to-teal-500',
  accounting: 'from-amber-500 to-yellow-500',
  video: 'from-pink-500 to-rose-500',
  recruiter: 'from-violet-500 to-purple-500',
  legal: 'from-slate-500 to-gray-500',
  analytics: 'from-teal-500 to-emerald-500',
  trends: 'from-lime-500 to-green-500',
}

export default function AgentsPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(true)
  const [recommendedIds, setRecommendedIds] = useState<string[]>([])

  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => {
      if (!user) return router.push('/login')
      const onboarding: OnboardingData | null = user.user_metadata?.onboarding_data || null
      setRecommendedIds(getRecommendedAgentIds(onboarding))
      setLoading(false)
    })
  }, [router])

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
            {AGENTS.filter(a => recommendedIds.includes(a.id)).map((agent) => (
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
            {AGENTS.map((agent) => {
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
                        ? 'bg-violet-500/10 text-violet-400'
                        : 'bg-purple-500/10 text-purple-400'
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
      </div>
    </div>
  )
}
