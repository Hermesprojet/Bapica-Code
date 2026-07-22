'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { BellRing, Send, Check, X, Trash2, Loader2, AlertCircle, CalendarClock } from 'lucide-react'

interface ReminderRow {
  id: string
  client: string
  contact_email: string | null
  invoice_ref: string | null
  amount: number | null
  currency: string | null
  stage: string
  due_on: string
  subject: string | null
  status: string
}

const STAGE_LABEL: Record<string, string> = { amiable: 'Amiable', ferme: 'Ferme', mise_en_demeure: 'Mise en demeure' }
const STATUS_LABEL: Record<string, string> = { scheduled: 'Programmée', sent: 'Envoyée', cancelled: 'Annulée', paid: 'Payée' }

export default function RemindersPage() {
  const [rows, setRows] = useState<ReminderRow[]>([])
  const [loading, setLoading] = useState(true)
  const [needsSetup, setNeedsSetup] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState<{ kind: 'ok' | 'err'; msg: string } | null>(null)

  const token = async () => (await supabase.auth.getSession()).data.session?.access_token || ''
  const today = new Date().toISOString().slice(0, 10)

  const load = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/reminders', { headers: { Authorization: `Bearer ${await token()}` } })
      const data = await res.json()
      if (res.ok) { setRows(data.reminders || []); setNeedsSetup(Boolean(data.needsSetup)) }
    } catch { /* ignore */ }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const act = async (id: string, action: 'prepare_email' | 'paid' | 'cancelled') => {
    setBusy(id); setNotice(null)
    try {
      const res = await fetch('/api/reminders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
        body: JSON.stringify({ id, action }),
      })
      const data = await res.json()
      if (res.ok && data.success) {
        setNotice({ kind: 'ok', msg: action === 'prepare_email' ? 'Email préparé dans « Actions à valider ».' : action === 'paid' ? 'Marquée payée.' : 'Relance annulée.' })
      } else setNotice({ kind: 'err', msg: data.error || 'Échec.' })
    } catch { setNotice({ kind: 'err', msg: 'Erreur de connexion.' }) }
    setBusy(null)
    load()
  }

  const remove = async (id: string) => {
    setBusy(id)
    try {
      await fetch('/api/reminders', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
        body: JSON.stringify({ id }),
      })
    } catch { /* ignore */ }
    setBusy(null)
    load()
  }

  return (
    <div>
      <div className="reveal mb-6">
        <h1 className="text-2xl font-bold">Relances</h1>
        <p className="mt-1 text-muted-foreground">
          Les relances d&apos;impayés programmées par Claire (J+7 amiable → J+15 ferme → J+30 mise en demeure).
          Envoyez-les d&apos;un clic (via « Actions à valider ») ou marquez la facture payée.
        </p>
      </div>

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
            La table <code className="rounded bg-muted px-1">payment_reminders</code> est absente : exécutez
            <code className="rounded bg-muted px-1">bapica/supabase-schema.sql</code> dans Supabase → SQL Editor.
          </p>
        </div>
      ) : rows.length === 0 ? (
        <div className="card-professional flex items-center gap-3 p-6 text-sm text-muted-foreground">
          <BellRing className="h-5 w-5 text-primary" />
          Aucune relance programmée. Demandez à Claire : « programme les relances pour la facture… ».
        </div>
      ) : (
        <div className="space-y-2">
          {rows.map((r) => {
            const isDue = r.status === 'scheduled' && r.due_on <= today
            return (
              <div key={r.id} className={`card-professional p-4 ${isDue ? 'border-amber-500/40' : ''}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-muted px-2.5 py-0.5 text-[11px] font-medium">{STAGE_LABEL[r.stage] || r.stage}</span>
                  <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] ${isDue ? 'bg-amber-500/10 text-amber-700' : 'bg-muted text-muted-foreground'}`}>
                    <CalendarClock className="h-3 w-3" /> {isDue ? 'À envoyer' : STATUS_LABEL[r.status] || r.status} · {new Date(r.due_on).toLocaleDateString('fr')}
                  </span>
                </div>
                <div className="mt-2 text-sm font-medium">
                  {r.client}
                  {r.invoice_ref ? <span className="text-muted-foreground"> · facture {r.invoice_ref}</span> : null}
                  {typeof r.amount === 'number' ? <span className="text-muted-foreground"> · {r.amount} {r.currency || 'EUR'}</span> : null}
                </div>
                {r.subject && <div className="mt-1 truncate text-xs text-muted-foreground">{r.subject}</div>}

                {r.status === 'scheduled' && (
                  <div className="mt-3 flex flex-wrap items-center justify-end gap-2">
                    <button onClick={() => act(r.id, 'cancelled')} disabled={busy === r.id} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground hover:text-destructive disabled:opacity-50">
                      <X className="h-3.5 w-3.5" /> Annuler
                    </button>
                    <button onClick={() => act(r.id, 'paid')} disabled={busy === r.id} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-muted disabled:opacity-50">
                      <Check className="h-3.5 w-3.5" /> Payée
                    </button>
                    <button onClick={() => act(r.id, 'prepare_email')} disabled={busy === r.id || !r.contact_email} title={r.contact_email ? '' : 'Aucun email de contact'} className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
                      {busy === r.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />} Préparer l&apos;email
                    </button>
                  </div>
                )}
                {r.status !== 'scheduled' && (
                  <div className="mt-3 flex justify-end">
                    <button onClick={() => remove(r.id)} disabled={busy === r.id} className="text-muted-foreground hover:text-destructive transition-colors" aria-label="Supprimer">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
