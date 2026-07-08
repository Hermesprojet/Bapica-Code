'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { analyzeBusinessProfile, type BusinessProfile } from '@/lib/business-profile'
import { type OnboardingData } from '@/lib/personalization'
import { DashboardSkeleton } from '@/components/ui/base'
import { 
  TrendingUp, AlertTriangle, Lightbulb, Target, 
  Clock, BarChart3, Zap, Shield, Loader2, Brain,
  ArrowRight, Check
} from 'lucide-react'

interface AIAnalysis {
  strategicMemo?: string
  keyInsight?: string
  growthForecast?: string
  top3Recommendations?: string[]
  healthScore?: number
}

export default function BusinessProfilePage() {
  const router = useRouter()
  const [loading, setLoading] = useState(true)
  const [profile, setProfile] = useState<BusinessProfile | null>(null)
  const [aiAnalysis, setAiAnalysis] = useState<AIAnalysis | null>(null)
  const [aiLoading, setAiLoading] = useState(false)

  useEffect(() => {
    supabase.auth.getUser().then(async ({ data: { user } }) => {
      if (!user) { router.push('/login'); return }
      const onboarded = user.user_metadata?.onboarding_completed
      if (!onboarded) { router.push('/onboarding'); return }

      const onboardingData = user.user_metadata?.onboarding_data || {}
      const prof = analyzeBusinessProfile(onboardingData)
      setProfile(prof)
      setLoading(false)

      // Lancer l'analyse IA
      setAiLoading(true)
      try {
        const res = await fetch('/api/business-analysis', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ profile: prof })
        })
        const data = await res.json()
        if (!data.error) setAiAnalysis(data)
      } catch {}
      setAiLoading(false)
    })
  }, [router])

  if (loading) return <DashboardSkeleton />
  if (!profile) return null

  const healthColor = aiAnalysis?.healthScore 
    ? aiAnalysis.healthScore >= 80 ? 'text-green-500' 
    : aiAnalysis.healthScore >= 60 ? 'text-amber-500' 
    : 'text-red-500'
  : 'text-muted-foreground'

  return (
    <div>
      {/* En-tête */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Brain className="h-8 w-8 text-primary" />
          <h1 className="text-2xl font-bold">Profil Business</h1>
        </div>
        <p className="text-muted-foreground">
          Analyse complète de {profile.companyName} — diagnostic stratégique IA
        </p>
      </div>

      {/* Score de santé */}
      <div className="card-professional mb-8 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-lg mb-1">Score de Santé Business</h3>
            <p className="text-sm text-muted-foreground">Analyse IA basée sur votre profil complet</p>
          </div>
          <div className="text-center">
            {aiLoading ? (
              <Loader2 className="h-12 w-12 animate-spin text-primary" />
            ) : (
              <>
                <div className={`text-5xl font-bold ${healthColor}`}>
                  {aiAnalysis?.healthScore || profile.maturityScore || '—'}
                </div>
                <div className="text-xs text-muted-foreground mt-1">/100</div>
              </>
            )}
          </div>
        </div>
        {aiAnalysis?.keyInsight && (
          <div className="mt-4 rounded-lg bg-muted/50 p-4">
            <div className="flex items-center gap-2 mb-2">
              <Lightbulb className="h-4 w-4 text-amber-500" />
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Insight clé</span>
            </div>
            <p className="text-sm">{aiAnalysis.keyInsight}</p>
          </div>
        )}
      </div>

      {/* Analyse stratégique IA */}
      {aiAnalysis?.strategicMemo && (
        <div className="card-professional mb-8 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Brain className="h-5 w-5 text-purple-500" />
            <h3 className="font-semibold">Analyse Stratégique IA</h3>
          </div>
          <p className="text-muted-foreground leading-relaxed mb-4">{aiAnalysis.strategicMemo}</p>
          {aiAnalysis.growthForecast && (
            <div className="rounded-lg bg-green-50 dark:bg-green-950/10 p-4">
              <div className="flex items-center gap-2 mb-1">
                <TrendingUp className="h-4 w-4 text-green-600" />
                <span className="text-sm font-semibold text-green-700 dark:text-green-400">Prévision de croissance</span>
              </div>
              <p className="text-sm text-green-700/80 dark:text-green-400/80">{aiAnalysis.growthForecast}</p>
            </div>
          )}
        </div>
      )}

      {/* KPIs */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        {[
          { label: 'Stade', value: profile.stage === 'early' ? 'Démarrage' : profile.stage === 'growth' ? 'Croissance' : profile.stage === 'scaleup' ? 'Scale-up' : 'Maturité', icon: Zap, color: 'text-blue-500' },
          { label: 'Maturité digitale', value: profile.digitalMaturity === 'high' ? 'Élevée' : profile.digitalMaturity === 'medium' ? 'Moyenne' : 'À développer', icon: BarChart3, color: 'text-purple-500' },
          { label: 'Urgence', value: profile.urgencyLevel === 'critical' ? 'Critique' : profile.urgencyLevel === 'high' ? 'Élevée' : 'Modérée', icon: Clock, color: profile.urgencyLevel === 'critical' ? 'text-red-500' : 'text-amber-500' },
          { label: 'Position marché', value: profile.marketPosition === 'leader' ? 'Leader' : profile.marketPosition === 'challenger' ? 'Challenger' : 'Niche', icon: Target, color: 'text-green-500' },
        ].map((kpi, i) => (
          <div key={i} className="card-professional p-4">
            <kpi.icon className={`h-5 w-5 ${kpi.color} mb-2`} />
            <div className="text-2xl font-bold">{kpi.value}</div>
            <div className="text-xs text-muted-foreground">{kpi.label}</div>
          </div>
        ))}
      </div>

      {/* Recommandations */}
      {aiAnalysis?.top3Recommendations && (
        <div className="card-professional mb-8 p-6">
          <h3 className="font-semibold text-lg mb-4">🎯 Recommandations Stratégiques IA</h3>
          <div className="space-y-3">
            {aiAnalysis.top3Recommendations.map((rec, i) => (
              <div key={i} className="flex items-start gap-3">
                <div className="shrink-0 mt-0.5 w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center">
                  <Check className="h-3.5 w-3.5 text-primary" />
                </div>
                <p className="text-sm text-muted-foreground">{rec}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Benchmarks sectoriels */}
      <div className="card-professional mb-8 p-6">
        <h3 className="font-semibold text-lg mb-4">📊 Benchmarks Sectoriels</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-xs text-muted-foreground">
                <th className="text-left py-2 font-medium">Métrique</th>
                <th className="text-left py-2 font-medium">Vous</th>
                <th className="text-left py-2 font-medium">Moyenne secteur</th>
                <th className="text-left py-2 font-medium">Opportunité</th>
              </tr>
            </thead>
            <tbody>
              {profile.industryBenchmarks?.map((b, i) => (
                <tr key={i} className="border-b border-border/50">
                  <td className="py-2 font-medium">{b.metric}</td>
                  <td className="py-2">{b.yourValue}</td>
                  <td className="py-2 text-muted-foreground">{b.industryAverage}</td>
                  <td className="py-2 text-xs text-green-600">{b.opportunity}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ROI + Plan d'action */}
      <div className="grid gap-6 md:grid-cols-2 mb-8">
        <div className="card-professional p-6">
          <h3 className="font-semibold text-lg mb-4">💰 ROI Estimé</h3>
          <div className="space-y-3">
            {profile.roiEstimates?.map((r, i) => (
              <div key={i} className={`flex items-center justify-between ${i === profile.roiEstimates!.length - 1 ? 'pt-3 border-t border-border font-semibold' : ''} text-sm`}>
                <span className="text-muted-foreground">{r.area}</span>
                <span className="font-medium text-green-600">{r.costSaved}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="card-professional p-6">
          <h3 className="font-semibold text-lg mb-4">🎯 Actions Prioritaires</h3>
          <div className="space-y-3">
            {profile.priorityActions?.map((a, i) => (
              <div key={i} className="flex items-start gap-3 text-sm">
                <span className={`shrink-0 mt-0.5 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                  a.timeframe === 'immediate' ? 'bg-red-500/10 text-red-500' :
                  a.timeframe === '1-month' ? 'bg-amber-500/10 text-amber-500' :
                  'bg-blue-500/10 text-blue-500'
                }`}>{i + 1}</span>
                <div>
                  <p className="text-muted-foreground">{a.action}</p>
                  <div className="flex gap-2 mt-1">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                      a.impact === 'transformational' ? 'bg-purple-500/10 text-purple-500' :
                      a.impact === 'high' ? 'bg-amber-500/10 text-amber-500' :
                      'bg-blue-500/10 text-blue-500'
                    }`}>Impact {a.impact}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground">
                      {a.timeframe === 'immediate' ? 'Immédiat' : a.timeframe === '1-month' ? '1 mois' : '3 mois'}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Risques détaillés */}
      <div className="card-professional p-6">
        <h3 className="font-semibold text-lg mb-4">⚠️ Analyse des Risques</h3>
        <div className="space-y-4">
          {profile.riskFactors?.map((r, i) => {
            const risk = typeof r === 'string' ? { risk: r, severity: 'medium' as const, probability: 50, mitigation: '' } : r
            return (
              <div key={i} className="flex items-start gap-4 p-4 rounded-lg bg-muted/30">
                <span className={`shrink-0 mt-1 w-3 h-3 rounded-full ${
                  risk.severity === 'critical' ? 'bg-red-500' :
                  risk.severity === 'high' ? 'bg-amber-500' :
                  'bg-blue-400'
                }`} />
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium text-sm">{risk.risk}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                      risk.severity === 'critical' ? 'bg-red-500/10 text-red-500' :
                      risk.severity === 'high' ? 'bg-amber-500/10 text-amber-500' :
                      'bg-blue-500/10 text-blue-500'
                    }`}>{risk.severity}</span>
                  </div>
                  <p className="text-xs text-muted-foreground mb-1">Probabilité : {risk.probability}%</p>
                  {risk.mitigation && (
                    <p className="text-xs text-green-600">→ {risk.mitigation}</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
