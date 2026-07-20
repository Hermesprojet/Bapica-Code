'use client'

import { useState } from 'react'
import { supabase } from '@/lib/supabase'
import { Loader2, Sparkles, AlertCircle, TrendingUp } from 'lucide-react'

interface Proposal { action: string; impact: string; effort: string }
interface Theme { titre: string; frequence: number; constat: string; exemples: string[]; propositions: Proposal[] }
interface Report { resume: string; themes: Theme[] }

const badge = (level: string) => {
  const l = level.toLowerCase()
  if (l === 'fort') return 'bg-green-500/10 text-green-700'
  if (l === 'moyen') return 'bg-amber-500/10 text-amber-700'
  return 'bg-muted text-muted-foreground'
}

export default function InsightsPage() {
  const [loading, setLoading] = useState(false)
  const [report, setReport] = useState<Report | null>(null)
  const [count, setCount] = useState(0)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  const token = async () => (await supabase.auth.getSession()).data.session?.access_token || ''

  const generate = async () => {
    setLoading(true); setError(''); setMsg(''); setReport(null)
    try {
      const res = await fetch('/api/insights', { headers: { Authorization: `Bearer ${await token()}` } })
      const data = await res.json()
      if (res.ok) {
        setReport(data.report || null)
        setCount(data.count || 0)
        if (!data.report) setMsg(data.message || 'Pas encore de données.')
      } else {
        setError(data.error || 'Impossible de générer le rapport.')
      }
    } catch {
      setError('Erreur de connexion.')
    }
    setLoading(false)
  }

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Apprentissage produit</h1>
          <p className="mt-1 text-muted-foreground">
            Bapica apprend de l&apos;expérience de vos clients (questions, feedback, échecs) et propose
            des améliorations priorisées. Réservé à l&apos;administrateur.
          </p>
        </div>
        <button
          onClick={generate}
          disabled={loading}
          className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Analyse…</> : <><Sparkles className="h-4 w-4" /> Générer le rapport</>}
        </button>
      </div>

      {error && (
        <div className="mb-6 flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}

      {msg && !report && (
        <div className="card-professional p-6 text-sm text-muted-foreground">{msg}</div>
      )}

      {report && (
        <div className="space-y-6">
          <div className="card-elevated p-5">
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Synthèse — {count} signaux analysés</div>
            <p className="mt-2 text-sm">{report.resume}</p>
          </div>

          {report.themes?.map((t, i) => (
            <div key={i} className="card-professional p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="flex items-center gap-2 font-semibold">
                  <TrendingUp className="h-4 w-4 text-primary" /> {t.titre}
                </h2>
                <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs text-muted-foreground">{t.frequence} signaux</span>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{t.constat}</p>

              {t.exemples?.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {t.exemples.map((ex, j) => (
                    <li key={j} className="text-xs italic text-muted-foreground">« {ex} »</li>
                  ))}
                </ul>
              )}

              {t.propositions?.length > 0 && (
                <div className="mt-3 space-y-2 border-t border-border pt-3">
                  {t.propositions.map((p, j) => (
                    <div key={j} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border p-3">
                      <span className="text-sm">{p.action}</span>
                      <span className="flex shrink-0 gap-1.5 text-[11px]">
                        <span className={`rounded px-2 py-0.5 ${badge(p.impact)}`}>impact {p.impact}</span>
                        <span className={`rounded px-2 py-0.5 ${badge(p.effort === 'faible' ? 'fort' : p.effort === 'fort' ? 'faible' : 'moyen')}`}>effort {p.effort}</span>
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}

          <p className="text-xs text-muted-foreground">
            Pour appliquer une amélioration : copiez la proposition et apportez-la dans une session Claude Code
            (implémentation + déploiement avec votre validation).
          </p>
        </div>
      )}
    </div>
  )
}
