'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { Workflow, Check, Pause, Play, Trash2, Loader2, AlertCircle, Clock } from 'lucide-react'

interface AutoRow {
  id: string
  agent_id: string | null
  title: string
  description: string
  cron: string
  schedule_label: string | null
  status: string
  last_run_at: string | null
}

const STATUS_LABEL: Record<string, string> = { pending: 'À valider', active: 'Active', paused: 'En pause' }

export default function AutomationsPage() {
  const [rows, setRows] = useState<AutoRow[]>([])
  const [loading, setLoading] = useState(true)
  const [needsSetup, setNeedsSetup] = useState(false)
  const [n8n, setN8n] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState<{ kind: 'ok' | 'err'; msg: string } | null>(null)

  const token = async () => (await supabase.auth.getSession()).data.session?.access_token || ''

  const load = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/automations', { headers: { Authorization: `Bearer ${await token()}` } })
      const data = await res.json()
      if (res.ok) { setRows(data.automations || []); setNeedsSetup(Boolean(data.needsSetup)); setN8n(Boolean(data.n8n)) }
    } catch { /* ignore */ }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const act = async (id: string, action: 'approve' | 'pause' | 'resume' | 'delete') => {
    setBusy(id); setNotice(null)
    try {
      const res = await fetch('/api/automations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
        body: JSON.stringify({ id, action }),
      })
      const data = await res.json()
      if (res.ok && data.success) {
        setNotice({ kind: 'ok', msg: data.note || (action === 'delete' ? 'Automatisation supprimée.' : action === 'pause' ? 'Mise en pause.' : 'Automatisation activée.') })
      } else setNotice({ kind: 'err', msg: data.error || 'Échec.' })
    } catch { setNotice({ kind: 'err', msg: 'Erreur de connexion.' }) }
    setBusy(null)
    load()
  }

  return (
    <div>
      <div className="reveal mb-6">
        <h1 className="text-2xl font-bold">Automatisations</h1>
        <p className="mt-1 text-muted-foreground">
          Vos agents proposent d&apos;automatiser les tâches récurrentes (rapports, veille, résumés…).
          Rien ne tourne sans votre accord : vous validez, N8N déclenche à la planification prévue.
        </p>
      </div>

      {!n8n && !needsSetup && (
        <div className="mb-6 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm text-amber-700">
          N8N n&apos;est pas encore branché : les automatisations validées sont enregistrées mais ne se
          déclencheront qu&apos;une fois N8N configuré (variables <code className="rounded bg-muted px-1">N8N_URL</code> / <code className="rounded bg-muted px-1">N8N_API_KEY</code>).
        </div>
      )}

      {notice && (
        <div className={`mb-6 rounded-xl border p-4 text-sm ${notice.kind === 'ok' ? 'border-green-500/30 bg-green-500/5 text-green-700' : 'border-destructive/30 bg-destructive/5 text-destructive'}`}>
          {notice.msg}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
      ) : needsSetup ? (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-5 text-sm">
          <div className="flex items-center gap-2 font-semibold text-amber-700"><AlertCircle className="h-4 w-4" /> Base non initialisée</div>
          <p className="mt-2 text-muted-foreground">
            La table <code className="rounded bg-muted px-1">automations</code> est absente : exécutez
            <code className="rounded bg-muted px-1">bapica/supabase-schema.sql</code> dans Supabase → SQL Editor.
          </p>
        </div>
      ) : rows.length === 0 ? (
        <div className="card-professional flex items-center gap-3 p-6 text-sm text-muted-foreground">
          <Workflow className="h-5 w-5 text-primary" />
          Aucune automatisation. Demandez par exemple à Claire « automatise un rapport de trésorerie chaque lundi ».
        </div>
      ) : (
        <div className="space-y-3">
          {rows.map((r) => (
            <div key={r.id} className={`card-professional p-5 ${r.status === 'pending' ? 'border-amber-500/40' : ''}`}>
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${r.status === 'active' ? 'bg-green-500/10 text-green-700' : r.status === 'pending' ? 'bg-amber-500/10 text-amber-700' : 'bg-muted text-muted-foreground'}`}>
                  {STATUS_LABEL[r.status] || r.status}
                </span>
                <span className="inline-flex items-center gap-1 rounded bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                  <Clock className="h-3 w-3" /> {r.schedule_label || r.cron}
                </span>
                {r.agent_id && <span className="rounded bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">{r.agent_id}</span>}
              </div>
              <p className="text-sm font-medium">{r.title}</p>
              <p className="mt-1 text-xs text-muted-foreground">{r.description}</p>
              {r.last_run_at && <p className="mt-1 text-[11px] text-muted-foreground">Dernière exécution : {new Date(r.last_run_at).toLocaleString('fr')}</p>}

              <div className="mt-4 flex flex-wrap items-center justify-end gap-2">
                <button onClick={() => act(r.id, 'delete')} disabled={busy === r.id} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground hover:text-destructive disabled:opacity-50">
                  <Trash2 className="h-3.5 w-3.5" /> Supprimer
                </button>
                {r.status === 'active' ? (
                  <button onClick={() => act(r.id, 'pause')} disabled={busy === r.id} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-muted disabled:opacity-50">
                    <Pause className="h-3.5 w-3.5" /> Mettre en pause
                  </button>
                ) : r.status === 'paused' ? (
                  <button onClick={() => act(r.id, 'resume')} disabled={busy === r.id} className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
                    <Play className="h-3.5 w-3.5" /> Réactiver
                  </button>
                ) : (
                  <button onClick={() => act(r.id, 'approve')} disabled={busy === r.id} className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
                    {busy === r.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />} Valider et activer
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
