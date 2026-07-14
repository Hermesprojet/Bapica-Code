'use client'

import { Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { Linkedin, Check, Loader2, Send, AlertCircle, Plus } from 'lucide-react'

// Plateformes : LinkedIn est branché ; les autres arriveront (natif, une par une).
const PLATFORMS = [
  { id: 'linkedin', label: 'LinkedIn', icon: Linkedin, color: 'text-[#0A66C2]', ready: true },
  { id: 'facebook', label: 'Facebook', icon: Plus, color: 'text-[#1877F2]', ready: false },
  { id: 'instagram', label: 'Instagram', icon: Plus, color: 'text-[#E4405F]', ready: false },
  { id: 'x', label: 'X (Twitter)', icon: Plus, color: 'text-foreground', ready: false },
]

export default function ConnectionsPage() {
  return (
    <Suspense fallback={<div className="flex justify-center py-20"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>}>
      <ConnectionsContent />
    </Suspense>
  )
}

function ConnectionsContent() {
  const params = useSearchParams()
  const [connected, setConnected] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState<{ kind: 'ok' | 'err'; msg: string } | null>(null)

  // Composer
  const [text, setText] = useState('')
  const [publishing, setPublishing] = useState(false)
  const [pubResult, setPubResult] = useState<string | null>(null)

  const token = async () => (await supabase.auth.getSession()).data.session?.access_token || ''

  const loadAccounts = async () => {
    try {
      const res = await fetch('/api/social/accounts', { headers: { Authorization: `Bearer ${await token()}` } })
      const data = await res.json()
      if (res.ok) setConnected(data.platforms || [])
    } catch { /* ignore */ }
    setLoading(false)
  }

  useEffect(() => {
    const c = params.get('connected')
    const e = params.get('error')
    if (c) setNotice({ kind: 'ok', msg: `${c} connecté avec succès.` })
    if (e) setNotice({ kind: 'err', msg: e })
    loadAccounts()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const connect = async (platform: string) => {
    if (platform !== 'linkedin') return
    // Navigation plein écran (OAuth) : on passe le jeton en query pour l'auth.
    window.location.href = `/api/social/linkedin/connect?t=${encodeURIComponent(await token())}`
  }

  const disconnect = async (platform: string) => {
    await fetch('/api/social/accounts', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
      body: JSON.stringify({ platform }),
    })
    loadAccounts()
  }

  const publish = async () => {
    if (!text.trim() || publishing) return
    setPublishing(true); setPubResult(null)
    try {
      const res = await fetch('/api/social/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
        body: JSON.stringify({ text, platforms: ['linkedin'] }),
      })
      const data = await res.json()
      if (data?.results?.linkedin?.ok) { setPubResult('✅ Publié sur LinkedIn.'); setText('') }
      else setPubResult('❌ ' + (data?.results?.linkedin?.error || data?.error || 'Échec de la publication.'))
    } catch {
      setPubResult('❌ Erreur de connexion.')
    }
    setPublishing(false)
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Connexions</h1>
        <p className="mt-1 text-muted-foreground">Reliez vos réseaux sociaux pour que Camille publie à votre place.</p>
      </div>

      {notice && (
        <div className={`mb-6 rounded-xl border p-4 text-sm ${notice.kind === 'ok' ? 'border-green-500/30 bg-green-500/5 text-green-700' : 'border-destructive/30 bg-destructive/5 text-destructive'}`}>
          {notice.msg}
        </div>
      )}

      {/* Plateformes */}
      <div className="grid gap-4 sm:grid-cols-2">
        {PLATFORMS.map((p) => {
          const Icon = p.icon
          const isConnected = connected.includes(p.id)
          return (
            <div key={p.id} className="card-professional flex items-center justify-between gap-3 p-4">
              <div className="flex items-center gap-3">
                <Icon className={`h-6 w-6 ${p.color}`} />
                <div>
                  <div className="font-semibold text-sm">{p.label}</div>
                  <div className="text-xs text-muted-foreground">
                    {isConnected ? 'Connecté' : p.ready ? 'Non connecté' : 'Bientôt disponible'}
                  </div>
                </div>
              </div>
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              ) : isConnected ? (
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-green-600"><Check className="h-4 w-4" /></span>
                  <button onClick={() => disconnect(p.id)} className="text-xs text-muted-foreground hover:text-destructive">Déconnecter</button>
                </div>
              ) : p.ready ? (
                <button onClick={() => connect(p.id)} className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors">
                  Connecter
                </button>
              ) : (
                <span className="rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground">Bientôt</span>
              )}
            </div>
          )
        })}
      </div>

      {/* Composer publication (LinkedIn) */}
      {connected.includes('linkedin') && (
        <div className="card-elevated mt-8 p-6">
          <h2 className="mb-3 font-semibold text-sm">Publier sur LinkedIn</h2>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={5}
            placeholder="Collez ici le post créé par Camille, ou écrivez le vôtre…"
            className="w-full resize-none rounded-xl border border-border bg-background px-4 py-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <div className="mt-3 flex items-center justify-between">
            {pubResult ? (
              <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                {pubResult.startsWith('✅') ? <Check className="h-3.5 w-3.5 text-green-600" /> : <AlertCircle className="h-3.5 w-3.5 text-destructive" />}
                {pubResult.replace(/^[✅❌]\s*/, '')}
              </span>
            ) : <span />}
            <button
              onClick={publish}
              disabled={!text.trim() || publishing}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-all"
            >
              {publishing ? <><Loader2 className="h-4 w-4 animate-spin" /> Publication…</> : <><Send className="h-4 w-4" /> Publier</>}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
