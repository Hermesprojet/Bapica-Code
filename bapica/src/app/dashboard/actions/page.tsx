'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { Check, X, Loader2, ShieldCheck, AlertCircle, Clock } from 'lucide-react'

interface ActionRow {
  id: string
  agent_id: string | null
  provider: string
  method: string
  path: string
  body: unknown
  summary: string
  status: 'pending' | 'executed' | 'rejected' | 'failed'
  result: string | null
  created_at: string
}

const STATUS_LABEL: Record<ActionRow['status'], string> = {
  pending: 'En attente',
  executed: 'Exécutée',
  rejected: 'Refusée',
  failed: 'Échec',
}

export default function ActionsPage() {
  const [actions, setActions] = useState<ActionRow[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [needsSetup, setNeedsSetup] = useState(false)
  const [notice, setNotice] = useState<{ kind: 'ok' | 'err'; msg: string } | null>(null)

  const token = async () => (await supabase.auth.getSession()).data.session?.access_token || ''

  const load = async () => {
    try {
      const res = await fetch('/api/actions', { headers: { Authorization: `Bearer ${await token()}` } })
      const data = await res.json()
      if (res.ok) { setActions(data.actions || []); setNeedsSetup(Boolean(data.needsSetup)) }
    } catch { /* ignore */ }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const decide = async (id: string, decision: 'approve' | 'reject') => {
    setBusy(id); setNotice(null)
    try {
      const res = await fetch('/api/actions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
        body: JSON.stringify({ id, decision }),
      })
      const data = await res.json()
      if (res.ok && data.success) {
        // RDV validé : on télécharge l'événement d'agenda (.ics), importable Google/Outlook/Apple.
        if (decision === 'approve' && data.kind === 'ics' && typeof data.ics === 'string') {
          try {
            const blob = new Blob([data.ics], { type: 'text/calendar;charset=utf-8' })
            const url = URL.createObjectURL(blob)
            const link = document.createElement('a')
            link.href = url
            link.download = typeof data.filename === 'string' ? data.filename : 'rendez-vous.ics'
            document.body.appendChild(link)
            link.click()
            link.remove()
            URL.revokeObjectURL(url)
          } catch { /* téléchargement best-effort */ }
          setNotice({ kind: 'ok', msg: 'Rendez-vous prêt : le fichier .ics a été téléchargé, ouvrez-le pour l’ajouter à votre agenda.' })
        } else if (decision === 'approve' && data.kind === 'calendar') {
          setNotice({ kind: 'ok', msg: `Rendez-vous ajouté à votre ${data.provider || 'agenda'}.` })
        } else {
          setNotice({ kind: 'ok', msg: decision === 'approve' ? 'Action exécutée.' : 'Action refusée.' })
        }
      } else {
        setNotice({ kind: 'err', msg: data.error || 'Échec de l’opération.' })
      }
    } catch {
      setNotice({ kind: 'err', msg: 'Erreur de connexion.' })
    }
    setBusy(null)
    load()
  }

  const pending = actions.filter((a) => a.status === 'pending')
  const history = actions.filter((a) => a.status !== 'pending')

  return (
    <div>
      <div className="reveal mb-6">
        <h1 className="text-2xl font-bold">Actions à valider</h1>
        <p className="mt-1 text-muted-foreground">
          Vos agents ne modifient jamais rien sans votre accord. Ils préparent l&apos;action ici,
          vous validez d&apos;un clic.
        </p>
      </div>

      {notice && (
        <div className={`mb-6 rounded-xl border p-4 text-sm ${notice.kind === 'ok' ? 'border-green-500/30 bg-green-500/5 text-green-700' : 'border-destructive/30 bg-destructive/5 text-destructive'}`}>
          {notice.msg}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
      ) : (
        <>
          {needsSetup ? (
            <div className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-5 text-sm">
              <div className="flex items-center gap-2 font-semibold text-amber-700">
                <AlertCircle className="h-4 w-4" />
                Base de données non initialisée
              </div>
              <p className="mt-2 text-muted-foreground">
                La table <code className="rounded bg-muted px-1">pending_actions</code> est absente : le script
                SQL n&apos;a pas été exécuté (ou pas jusqu&apos;au bout). Ouvrez Supabase → SQL Editor, collez
                tout le contenu de <code className="rounded bg-muted px-1">bapica/supabase-schema.sql</code>,
                puis cliquez sur Run et rechargez cette page.
              </p>
            </div>
          ) : pending.length === 0 ? (
            <div className="card-professional flex items-center gap-3 p-6 text-sm text-muted-foreground">
              <ShieldCheck className="h-5 w-5 text-green-600" />
              Aucune action en attente — la base est bien initialisée. Demandez par exemple à Claire de préparer une facture.
            </div>
          ) : (
            <div className="space-y-3">
              {pending.map((a) => (
                <div key={a.id} className="card-elevated p-5">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-medium text-amber-700">
                      <Clock className="h-3 w-3" /> En attente
                    </span>
                    {a.agent_id && <span className="rounded bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">{a.agent_id}</span>}
                    <span className="rounded bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">{a.provider}</span>
                  </div>

                  <p className="text-sm font-medium">{a.summary}</p>

                  <details className="mt-2">
                    <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
                      Voir le détail technique
                    </summary>
                    <pre className="mt-2 max-h-48 overflow-auto rounded-lg border border-border bg-muted p-3 text-[11px]">
{a.method} {a.path}
{a.body ? JSON.stringify(a.body, null, 2) : ''}
                    </pre>
                  </details>

                  <div className="mt-4 flex items-center justify-end gap-2">
                    <button
                      onClick={() => decide(a.id, 'reject')}
                      disabled={busy === a.id}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs font-medium text-muted-foreground hover:text-destructive disabled:opacity-50 transition-colors"
                    >
                      <X className="h-3.5 w-3.5" /> Refuser
                    </button>
                    <button
                      onClick={() => decide(a.id, 'approve')}
                      disabled={busy === a.id}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
                    >
                      {busy === a.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                      Valider et exécuter
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {history.length > 0 && (
            <div className="mt-10">
              <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Historique</h2>
              <div className="space-y-2">
                {history.map((a) => (
                  <div key={a.id} className="card-professional p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-sm">{a.summary}</span>
                      <span className={`inline-flex items-center gap-1 text-[11px] ${a.status === 'executed' ? 'text-green-600' : a.status === 'failed' ? 'text-destructive' : 'text-muted-foreground'}`}>
                        {a.status === 'executed' ? <Check className="h-3 w-3" /> : a.status === 'failed' ? <AlertCircle className="h-3 w-3" /> : <X className="h-3 w-3" />}
                        {STATUS_LABEL[a.status]}
                      </span>
                    </div>
                    {a.result && a.status === 'failed' && (
                      <p className="mt-1 break-all text-[11px] text-destructive">{a.result.slice(0, 300)}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
