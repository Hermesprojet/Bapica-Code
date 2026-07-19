'use client'

import { useState } from 'react'
import { Phone, Loader2, Check, AlertCircle, PhoneOutgoing } from 'lucide-react'
import { supabase } from '@/lib/supabase'

/**
 * Panneau « Lancer un appel » pour les agents vocaux (Nadia/Hugo).
 * Alimente POST /api/vapi/create-call (appel sortant réel via Vapi si les clés
 * VAPI_* sont configurées ; sinon message « Configuration Vapi manquante »).
 */
export function VapiCallPanel({ persona }: { persona: string }) {
  const [open, setOpen] = useState(false)
  const [phoneNumber, setPhoneNumber] = useState('')
  const [prospectName, setProspectName] = useState('')
  const [context, setContext] = useState('')
  const [status, setStatus] = useState<'idle' | 'calling' | 'ok' | 'err'>('idle')
  const [message, setMessage] = useState('')

  const launchCall = async () => {
    if (!phoneNumber.trim() || status === 'calling') return
    setStatus('calling')
    setMessage('')
    try {
      const { data: { session } } = await supabase.auth.getSession()
      const token = session?.access_token || ''
      const res = await fetch('/api/vapi/create-call', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ phoneNumber: phoneNumber.trim(), prospectName: prospectName.trim(), context: context.trim() }),
      })
      const data = await res.json()
      if (res.ok && data.success) {
        setStatus('ok')
        setMessage(`Appel lancé (réf. ${data.callId}). ${persona} rappellera un compte rendu.`)
      } else {
        setStatus('err')
        setMessage(data.error || "Impossible de lancer l'appel.")
      }
    } catch {
      setStatus('err')
      setMessage('Erreur de connexion.')
    }
  }

  return (
    <div className="rounded-xl border border-border bg-card">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-sm font-semibold"
      >
        <span className="flex items-center gap-2">
          <PhoneOutgoing className="h-4 w-4 text-primary" />
          Lancer un appel avec {persona}
        </span>
        <span className="text-xs text-muted-foreground">{open ? 'Fermer' : 'Ouvrir'}</span>
      </button>

      {open && (
        <div className="border-t border-border p-4 space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              type="tel"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              placeholder="Numéro (+33 6 12 34 56 78)"
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <input
              type="text"
              value={prospectName}
              onChange={(e) => setProspectName(e.target.value)}
              placeholder="Nom du prospect (optionnel)"
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
          <textarea
            value={context}
            onChange={(e) => setContext(e.target.value)}
            rows={3}
            placeholder="Contexte de l'appel : offre, objectif, points à aborder…"
            className="w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <div className="flex items-center justify-between gap-3">
            {message ? (
              <span className={`inline-flex items-center gap-1.5 text-xs ${status === 'ok' ? 'text-green-600' : 'text-destructive'}`}>
                {status === 'ok' ? <Check className="h-3.5 w-3.5" /> : <AlertCircle className="h-3.5 w-3.5" />}
                {message}
              </span>
            ) : <span />}
            <button
              onClick={launchCall}
              disabled={!phoneNumber.trim() || status === 'calling'}
              className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {status === 'calling' ? <><Loader2 className="h-4 w-4 animate-spin" /> Appel…</> : <><Phone className="h-4 w-4" /> Appeler</>}
            </button>
          </div>
          <p className="text-[11px] text-muted-foreground">
            L&apos;appel réel nécessite un compte Vapi configuré (clés VAPI_API_KEY, VAPI_ASSISTANT_ID,
            VAPI_PHONE_NUMBER_ID). Sans configuration, un message vous l&apos;indiquera.
          </p>
        </div>
      )}
    </div>
  )
}
