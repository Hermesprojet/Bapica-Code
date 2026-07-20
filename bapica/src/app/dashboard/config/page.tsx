'use client'

import { useState, useEffect } from 'react'
import { supabase } from '@/lib/supabase'
import { Loader2, AlertCircle, CheckCircle2, XCircle, RefreshCw, ServerCog } from 'lucide-react'

interface GroupReport {
  id: string
  label: string
  required: boolean
  ready: boolean
  missing: string[]
  optionalMissing: string[]
}
interface EnvReport {
  ok: boolean
  missingRequired: string[]
  groups: GroupReport[]
}

export default function ConfigPage() {
  const [loading, setLoading] = useState(true)
  const [report, setReport] = useState<EnvReport | null>(null)
  const [error, setError] = useState('')

  const token = async () => (await supabase.auth.getSession()).data.session?.access_token || ''

  const load = async () => {
    setLoading(true); setError(''); setReport(null)
    try {
      const res = await fetch('/api/health/env', { headers: { Authorization: `Bearer ${await token()}` } })
      const data = await res.json()
      if (res.ok) {
        setReport(data as EnvReport)
      } else {
        setError(data.error || 'Impossible de charger le diagnostic.')
      }
    } catch {
      setError('Erreur de connexion.')
    }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const readyCount = report?.groups.filter((g) => g.ready).length ?? 0
  const total = report?.groups.length ?? 0

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <ServerCog className="h-6 w-6 text-primary" /> Configuration
          </h1>
          <p className="mt-1 text-muted-foreground">
            État des variables d&apos;environnement en production. Seule la <strong>présence</strong> de
            chaque variable est vérifiée — jamais sa valeur. Réservé à l&apos;administrateur.
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Chargement…</> : <><RefreshCw className="h-4 w-4" /> Rafraîchir</>}
        </button>
      </div>

      {error && (
        <div className="mb-6 flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}

      {report && (
        <div className="space-y-6">
          {/* Synthèse */}
          <div className={`card-elevated flex flex-wrap items-center justify-between gap-3 p-5 ${report.ok ? '' : 'border-amber-500/40'}`}>
            <div className="flex items-center gap-3">
              {report.ok
                ? <CheckCircle2 className="h-6 w-6 text-green-600" />
                : <AlertCircle className="h-6 w-6 text-amber-600" />}
              <div>
                <div className="font-semibold">
                  {report.ok ? 'Configuration de base complète' : 'Variables de base manquantes'}
                </div>
                <div className="text-sm text-muted-foreground">
                  {readyCount}/{total} fonctions entièrement configurées
                </div>
              </div>
            </div>
            {!report.ok && (
              <div className="text-sm text-amber-700">
                À renseigner dans Vercel : <span className="font-mono">{report.missingRequired.join(', ')}</span>
              </div>
            )}
          </div>

          {/* Groupes */}
          <div className="space-y-3">
            {report.groups.map((g) => (
              <div key={g.id} className="card-professional p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    {g.ready
                      ? <CheckCircle2 className="h-4 w-4 shrink-0 text-green-600" />
                      : <XCircle className={`h-4 w-4 shrink-0 ${g.required ? 'text-destructive' : 'text-muted-foreground'}`} />}
                    <span className="font-medium">{g.label}</span>
                    {g.required && (
                      <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">requis</span>
                    )}
                  </div>
                  <span className={`rounded-full px-2.5 py-0.5 text-xs ${g.ready ? 'bg-green-500/10 text-green-700' : 'bg-muted text-muted-foreground'}`}>
                    {g.ready ? 'Prêt' : 'À configurer'}
                  </span>
                </div>

                {(g.missing.length > 0 || g.optionalMissing.length > 0) && (
                  <div className="mt-3 space-y-1.5 border-t border-border pt-3">
                    {g.missing.map((v) => (
                      <div key={v} className="flex items-center gap-2 text-xs">
                        <XCircle className="h-3.5 w-3.5 shrink-0 text-destructive/70" />
                        <span className="font-mono">{v}</span>
                        <span className="text-muted-foreground">— manquante</span>
                      </div>
                    ))}
                    {g.optionalMissing.map((v) => (
                      <div key={v} className="flex items-center gap-2 text-xs text-muted-foreground">
                        <XCircle className="h-3.5 w-3.5 shrink-0 opacity-50" />
                        <span className="font-mono">{v}</span>
                        <span>— optionnelle</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          <p className="text-xs text-muted-foreground">
            Renseignez les variables dans Vercel → Settings → Environment Variables, puis
            <strong> redéployez le dernier déploiement</strong> (ne jamais « Redeploy » un ancien).
            Référence : <span className="font-mono">bapica/.env.example</span>.
          </p>
        </div>
      )}
    </div>
  )
}
