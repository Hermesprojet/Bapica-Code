'use client'

import { Suspense, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { Check, Loader2, Send, AlertCircle, Search, Link2, X } from 'lucide-react'
import { getAvailableIntegrations } from '@/lib/integrations'
import { connectMethodFor, soonReasonFor, apiKeyHintFor } from '@/lib/integrations-connect'

const CATALOG = getAvailableIntegrations()

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
  const [query, setQuery] = useState('')

  // Saisie de clé API (par plateforme)
  const [openKeyFor, setOpenKeyFor] = useState<string | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)

  // Composer LinkedIn
  const [text, setText] = useState('')
  const [publishing, setPublishing] = useState(false)
  const [pubResult, setPubResult] = useState<string | null>(null)

  const token = async () => (await supabase.auth.getSession()).data.session?.access_token || ''

  const loadConnections = async () => {
    try {
      const res = await fetch('/api/integrations', { headers: { Authorization: `Bearer ${await token()}` } })
      const data = await res.json()
      if (res.ok) setConnected(data.connected || [])
    } catch { /* ignore */ }
    setLoading(false)
  }

  useEffect(() => {
    const c = params.get('connected')
    const e = params.get('error')
    if (c) setNotice({ kind: 'ok', msg: `${c} connecté avec succès.` })
    if (e) setNotice({ kind: 'err', msg: e })
    loadConnections()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const connect = async (provider: string) => {
    const method = connectMethodFor(provider)
    if (method === 'oauth' && provider === 'linkedin') {
      window.location.href = `/api/social/linkedin/connect?t=${encodeURIComponent(await token())}`
      return
    }
    if (method === 'api_key') {
      setOpenKeyFor(provider); setApiKey(''); setNotice(null)
    }
  }

  const saveKey = async (provider: string) => {
    if (!apiKey.trim() || saving) return
    setSaving(true); setNotice(null)
    try {
      const res = await fetch('/api/integrations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
        body: JSON.stringify({ provider, apiKey: apiKey.trim() }),
      })
      const data = await res.json()
      if (res.ok && data.success) {
        setNotice({ kind: 'ok', msg: `${provider} connecté.` })
        setOpenKeyFor(null); setApiKey('')
        loadConnections()
      } else {
        setNotice({ kind: 'err', msg: data.error || 'Échec de la connexion.' })
      }
    } catch {
      setNotice({ kind: 'err', msg: 'Erreur de connexion.' })
    }
    setSaving(false)
  }

  const disconnect = async (provider: string) => {
    await fetch('/api/integrations', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
      body: JSON.stringify({ provider }),
    })
    loadConnections()
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
      if (data?.results?.linkedin?.ok) { setPubResult('Publié sur LinkedIn.'); setText('') }
      else setPubResult(data?.results?.linkedin?.error || data?.error || 'Échec de la publication.')
    } catch {
      setPubResult('Erreur de connexion.')
    }
    setPublishing(false)
  }

  // Filtrage + regroupement par catégorie
  const grouped = useMemo(() => {
    const q = query.trim().toLowerCase()
    const filtered = q
      ? CATALOG.filter((i) => i.name.toLowerCase().includes(q) || i.description.toLowerCase().includes(q) || i.category.toLowerCase().includes(q))
      : CATALOG
    const map = new Map<string, typeof CATALOG>()
    for (const item of filtered) {
      if (!map.has(item.category)) map.set(item.category, [])
      map.get(item.category)!.push(item)
    }
    return Array.from(map.entries())
  }, [query])

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Connexions</h1>
        <p className="mt-1 text-muted-foreground">
          Reliez vos outils à Bapica : boîte mail, comptabilité, banque, CRM, e-commerce, agenda…
          Vos agents s&apos;appuient dessus pour agir concrètement.
        </p>
      </div>

      {notice && (
        <div className={`mb-6 rounded-xl border p-4 text-sm ${notice.kind === 'ok' ? 'border-green-500/30 bg-green-500/5 text-green-700' : 'border-destructive/30 bg-destructive/5 text-destructive'}`}>
          {notice.msg}
        </div>
      )}

      {/* Recherche */}
      <div className="mb-6 flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Rechercher une plateforme (Stripe, Pennylane, Qonto, HubSpot…)"
            className="w-full rounded-lg border border-border bg-background py-2 pl-9 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
        <span className="shrink-0 text-xs text-muted-foreground">
          {loading ? '…' : `${connected.length} connectée${connected.length > 1 ? 's' : ''} / ${CATALOG.length}`}
        </span>
      </div>

      {/* Catalogue par catégorie */}
      <div className="space-y-8">
        {grouped.map(([category, items]) => (
          <section key={category}>
            <h2 className="mb-3 text-sm font-semibold text-muted-foreground">{category}</h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((item) => {
                const id = item.id as string
                const isConnected = connected.includes(id)
                const method = connectMethodFor(id)
                const isOpen = openKeyFor === id
                return (
                  <div key={id} className="card-professional p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex min-w-0 items-start gap-3">
                        <span className="text-xl leading-none">{item.icon}</span>
                        <div className="min-w-0">
                          <div className="text-sm font-semibold">{item.name}</div>
                          <div className="text-xs text-muted-foreground">{item.description}</div>
                        </div>
                      </div>
                      {isConnected && <Check className="h-4 w-4 shrink-0 text-green-600" />}
                    </div>

                    <div className="mt-3">
                      {isConnected ? (
                        <button onClick={() => disconnect(id)} className="text-xs text-muted-foreground hover:text-destructive transition-colors">
                          Déconnecter
                        </button>
                      ) : method === 'soon' ? (
                        <span className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-[11px] text-muted-foreground" title={soonReasonFor(id)}>
                          Bientôt
                        </span>
                      ) : (
                        <button
                          onClick={() => connect(id)}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
                        >
                          <Link2 className="h-3.5 w-3.5" />
                          Connecter
                        </button>
                      )}
                    </div>

                    {/* Saisie de la clé API */}
                    {isOpen && !isConnected && (
                      <div className="mt-3 border-t border-border pt-3">
                        <p className="mb-2 text-[11px] text-muted-foreground">{apiKeyHintFor(id)}</p>
                        <div className="flex items-center gap-2">
                          <input
                            type="password"
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                            placeholder="Coller la clé API"
                            className="min-w-0 flex-1 rounded-lg border border-border bg-background px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                          />
                          <button
                            onClick={() => saveKey(id)}
                            disabled={!apiKey.trim() || saving}
                            className="shrink-0 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                          >
                            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Valider'}
                          </button>
                          <button onClick={() => setOpenKeyFor(null)} className="shrink-0 text-muted-foreground hover:text-foreground" aria-label="Annuler">
                            <X className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </section>
        ))}
      </div>

      {/* Composer LinkedIn (si connecté) */}
      {connected.includes('linkedin') && (
        <div className="card-elevated mt-8 p-6">
          <h2 className="mb-3 text-sm font-semibold">Publier sur LinkedIn</h2>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={5}
            placeholder="Collez ici le post créé par Camille, ou écrivez le vôtre…"
            className="w-full resize-none rounded-xl border border-border bg-background px-4 py-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <div className="mt-3 flex items-center justify-between gap-3">
            {pubResult ? (
              <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                {pubResult.startsWith('Publié') ? <Check className="h-3.5 w-3.5 text-green-600" /> : <AlertCircle className="h-3.5 w-3.5 text-destructive" />}
                {pubResult}
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

      <p className="mt-8 text-xs text-muted-foreground">
        Les clés sont stockées côté serveur (accès restreint au service, jamais renvoyées au navigateur).
        Les plateformes « Bientôt » demandent une validation éditeur (Google, Microsoft, Meta) ou un
        agrégateur bancaire agréé — survolez le badge pour connaître la raison.
      </p>
    </div>
  )
}
