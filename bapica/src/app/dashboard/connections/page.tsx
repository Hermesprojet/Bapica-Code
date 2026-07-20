'use client'

import { Suspense, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { Check, Loader2, Send, AlertCircle, Search, Link2, X, Plus } from 'lucide-react'
import { getAvailableIntegrations } from '@/lib/integrations'
import { connectMethodFor, soonReasonFor, apiKeyHintFor } from '@/lib/integrations-connect'
import { EMAIL_PRESETS } from '@/lib/email-presets'
import { Mail } from 'lucide-react'

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

  // Plateformes hors catalogue ajoutées par le client
  const [custom, setCustom] = useState<{ platform: string; name: string; baseUrl: string; category: string }[]>([])
  const [cOpen, setCOpen] = useState(false)
  const [cName, setCName] = useState('')
  const [cUrl, setCUrl] = useState('')
  const [cKey, setCKey] = useState('')
  const [cCat, setCCat] = useState('Autre')
  const [cSaving, setCSaving] = useState(false)

  // Connexion email (IMAP/SMTP)
  const [emailConn, setEmailConn] = useState<{ connected: boolean; email: string } | null>(null)
  const [eOpen, setEOpen] = useState(false)
  const [eProvider, setEProvider] = useState('gmail')
  const [eEmail, setEEmail] = useState('')
  const [ePass, setEPass] = useState('')
  const [eImapHost, setEImapHost] = useState(EMAIL_PRESETS.gmail.imapHost)
  const [eImapPort, setEImapPort] = useState(EMAIL_PRESETS.gmail.imapPort)
  const [eSmtpHost, setESmtpHost] = useState(EMAIL_PRESETS.gmail.smtpHost)
  const [eSmtpPort, setESmtpPort] = useState(EMAIL_PRESETS.gmail.smtpPort)
  const [eSaving, setESaving] = useState(false)

  const onProvider = (key: string) => {
    setEProvider(key)
    const p = EMAIL_PRESETS[key]
    if (p) { setEImapHost(p.imapHost); setEImapPort(p.imapPort); setESmtpHost(p.smtpHost); setESmtpPort(p.smtpPort) }
  }

  const loadEmail = async () => {
    try {
      const res = await fetch('/api/integrations/email', { headers: { Authorization: `Bearer ${await token()}` } })
      if (res.ok) setEmailConn(await res.json())
    } catch { /* ignore */ }
  }

  const saveEmail = async () => {
    if (!eEmail.trim() || !ePass.trim() || eSaving) return
    setESaving(true); setNotice(null)
    try {
      const res = await fetch('/api/integrations/email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
        body: JSON.stringify({ email: eEmail.trim(), password: ePass, imapHost: eImapHost.trim(), imapPort: eImapPort, smtpHost: eSmtpHost.trim(), smtpPort: eSmtpPort }),
      })
      const data = await res.json()
      if (res.ok && data.success) {
        setNotice({ kind: 'ok', msg: `Boîte ${data.email} connectée.` })
        setEmailConn({ connected: true, email: data.email }); setEOpen(false); setEPass('')
      } else {
        setNotice({ kind: 'err', msg: data.error || 'Échec de la connexion email.' })
      }
    } catch {
      setNotice({ kind: 'err', msg: 'Erreur de connexion.' })
    }
    setESaving(false)
  }

  const disconnectEmail = async () => {
    await fetch('/api/integrations/email', { method: 'DELETE', headers: { Authorization: `Bearer ${await token()}` } })
    setEmailConn({ connected: false, email: '' })
  }

  // Connexion WordPress (audit + modification du site)
  const [wpConn, setWpConn] = useState<{ connected: boolean; siteUrl: string } | null>(null)
  const [wOpen, setWOpen] = useState(false)
  const [wSite, setWSite] = useState('')
  const [wUser, setWUser] = useState('')
  const [wPass, setWPass] = useState('')
  const [wSaving, setWSaving] = useState(false)

  const loadWordpress = async () => {
    try {
      const res = await fetch('/api/integrations/wordpress', { headers: { Authorization: `Bearer ${await token()}` } })
      if (res.ok) setWpConn(await res.json())
    } catch { /* ignore */ }
  }

  const saveWordpress = async () => {
    if (!wSite.trim() || !wUser.trim() || !wPass.trim() || wSaving) return
    setWSaving(true); setNotice(null)
    try {
      const res = await fetch('/api/integrations/wordpress', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
        body: JSON.stringify({ siteUrl: wSite.trim(), user: wUser.trim(), appPassword: wPass }),
      })
      const data = await res.json()
      if (res.ok && data.success) {
        setNotice({ kind: 'ok', msg: `Site ${data.siteUrl} connecté.` })
        setWpConn({ connected: true, siteUrl: data.siteUrl }); setWOpen(false); setWPass('')
      } else {
        setNotice({ kind: 'err', msg: data.error || 'Échec de la connexion WordPress.' })
      }
    } catch {
      setNotice({ kind: 'err', msg: 'Erreur de connexion.' })
    }
    setWSaving(false)
  }

  const disconnectWordpress = async () => {
    await fetch('/api/integrations/wordpress', { method: 'DELETE', headers: { Authorization: `Bearer ${await token()}` } })
    setWpConn({ connected: false, siteUrl: '' })
  }

  // Composer LinkedIn
  const [text, setText] = useState('')
  const [publishing, setPublishing] = useState(false)
  const [pubResult, setPubResult] = useState<string | null>(null)

  const token = async () => (await supabase.auth.getSession()).data.session?.access_token || ''

  const loadConnections = async () => {
    try {
      const res = await fetch('/api/integrations', { headers: { Authorization: `Bearer ${await token()}` } })
      const data = await res.json()
      if (res.ok) { setConnected(data.connected || []); setCustom(data.custom || []) }
    } catch { /* ignore */ }
    setLoading(false)
  }

  const addCustom = async () => {
    if (!cName.trim() || !cKey.trim() || cSaving) return
    setCSaving(true); setNotice(null)
    try {
      const res = await fetch('/api/integrations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
        body: JSON.stringify({ custom: true, name: cName.trim(), baseUrl: cUrl.trim(), category: cCat, apiKey: cKey.trim() }),
      })
      const data = await res.json()
      if (res.ok && data.success) {
        setNotice({ kind: 'ok', msg: `${data.name} ajouté à vos plateformes.` })
        setCName(''); setCUrl(''); setCKey(''); setCCat('Autre'); setCOpen(false)
        loadConnections()
      } else {
        setNotice({ kind: 'err', msg: data.error || 'Échec de l’ajout.' })
      }
    } catch {
      setNotice({ kind: 'err', msg: 'Erreur de connexion.' })
    }
    setCSaving(false)
  }

  useEffect(() => {
    const c = params.get('connected')
    const e = params.get('error')
    if (c) setNotice({ kind: 'ok', msg: `${c} connecté avec succès.` })
    if (e) setNotice({ kind: 'err', msg: e })
    loadConnections()
    loadEmail()
    loadWordpress()
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

      {/* Boîte email (IMAP/SMTP) — fonctionne avec tout fournisseur */}
      <div className="card-elevated mb-8 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            <Mail className="mt-0.5 h-5 w-5 text-primary" />
            <div>
              <div className="text-sm font-semibold">Boîte email (IMAP/SMTP)</div>
              <div className="text-xs text-muted-foreground">
                Connectez n&apos;importe quelle boîte (Gmail, Outlook, OVH…) pour que vos agents lisent et
                répondent à vos emails. {emailConn?.connected ? `Connectée : ${emailConn.email}` : ''}
              </div>
            </div>
          </div>
          {emailConn?.connected ? (
            <button onClick={disconnectEmail} className="text-xs text-muted-foreground hover:text-destructive transition-colors">Déconnecter</button>
          ) : !eOpen ? (
            <button onClick={() => setEOpen(true)} className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90">
              <Link2 className="h-3.5 w-3.5" /> Connecter ma boîte
            </button>
          ) : null}
        </div>

        {eOpen && !emailConn?.connected && (
          <div className="mt-4 space-y-3 border-t border-border pt-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <select value={eProvider} onChange={(e) => onProvider(e.target.value)} className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary">
                {Object.entries(EMAIL_PRESETS).map(([k, p]) => <option key={k} value={k}>{p.label}</option>)}
              </select>
              <input value={eEmail} onChange={(e) => setEEmail(e.target.value)} placeholder="Adresse email" className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
              <input type="password" value={ePass} onChange={(e) => setEPass(e.target.value)} placeholder="Mot de passe (ou mot de passe d'application)" className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary sm:col-span-2" />
              <input value={eImapHost} onChange={(e) => setEImapHost(e.target.value)} placeholder="Serveur IMAP" className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
              <input value={eSmtpHost} onChange={(e) => setESmtpHost(e.target.value)} placeholder="Serveur SMTP" className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
            </div>
            {EMAIL_PRESETS[eProvider]?.note && (
              <p className="text-[11px] text-amber-600">{EMAIL_PRESETS[eProvider].note}</p>
            )}
            <div className="flex items-center justify-end gap-2">
              <button onClick={() => setEOpen(false)} className="rounded-lg px-3 py-2 text-xs text-muted-foreground hover:text-foreground">Annuler</button>
              <button onClick={saveEmail} disabled={!eEmail.trim() || !ePass.trim() || eSaving} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
                {eSaving ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Vérification…</> : 'Connecter'}
              </button>
            </div>
            <p className="text-[11px] text-muted-foreground">
              On teste la connexion avant d&apos;enregistrer. Le mot de passe est stocké côté serveur,
              jamais renvoyé au navigateur. Les envois passent toujours par « Actions à valider ».
            </p>
          </div>
        )}
      </div>

      {/* Site WordPress (audit + modification par Camille) */}
      <div className="card-elevated mb-8 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            <Link2 className="mt-0.5 h-5 w-5 text-primary" />
            <div>
              <div className="text-sm font-semibold">Site WordPress</div>
              <div className="text-xs text-muted-foreground">
                Permet à Camille d&apos;auditer ET de modifier votre site (titres, contenus SEO) — toute
                modification passe par « Actions à valider ». {wpConn?.connected ? `Connecté : ${wpConn.siteUrl}` : ''}
              </div>
            </div>
          </div>
          {wpConn?.connected ? (
            <button onClick={disconnectWordpress} className="text-xs text-muted-foreground hover:text-destructive transition-colors">Déconnecter</button>
          ) : !wOpen ? (
            <button onClick={() => setWOpen(true)} className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90">
              <Link2 className="h-3.5 w-3.5" /> Connecter mon site
            </button>
          ) : null}
        </div>

        {wOpen && !wpConn?.connected && (
          <div className="mt-4 space-y-3 border-t border-border pt-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <input value={wSite} onChange={(e) => setWSite(e.target.value)} placeholder="URL du site (https://monsite.com)" className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary sm:col-span-2" />
              <input value={wUser} onChange={(e) => setWUser(e.target.value)} placeholder="Nom d'utilisateur WordPress" className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
              <input type="password" value={wPass} onChange={(e) => setWPass(e.target.value)} placeholder="Mot de passe d'application" className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
            </div>
            <p className="text-[11px] text-amber-600">
              Créez le mot de passe d&apos;application dans WordPress : Utilisateurs → Profil → « Mots de passe d&apos;application ». Ce n&apos;est pas votre mot de passe de connexion habituel.
            </p>
            <div className="flex items-center justify-end gap-2">
              <button onClick={() => setWOpen(false)} className="rounded-lg px-3 py-2 text-xs text-muted-foreground hover:text-foreground">Annuler</button>
              <button onClick={saveWordpress} disabled={!wSite.trim() || !wUser.trim() || !wPass.trim() || wSaving} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
                {wSaving ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Vérification…</> : 'Connecter'}
              </button>
            </div>
          </div>
        )}
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

      {/* Plateforme hors catalogue */}
      <div className="card-elevated mt-8 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Plus className="h-4 w-4 text-primary" />
              Votre plateforme n&apos;est pas dans la liste ?
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Ajoutez n&apos;importe quelle application, banque ou logiciel métier disposant d&apos;une API.
            </p>
          </div>
          {!cOpen && (
            <button
              onClick={() => setCOpen(true)}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs font-semibold hover:bg-muted transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              Ajouter une plateforme
            </button>
          )}
        </div>

        {cOpen && (
          <div className="mt-4 space-y-3 border-t border-border pt-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <input
                value={cName}
                onChange={(e) => setCName(e.target.value)}
                placeholder="Nom (ex : Ma Banque, Sellsy, Axonaut…)"
                className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <select
                value={cCat}
                onChange={(e) => setCCat(e.target.value)}
                className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              >
                {['Banque', 'Finance', 'CRM', 'Communication', 'E-commerce', 'Agenda', 'Projet', 'Autre'].map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
              <input
                value={cUrl}
                onChange={(e) => setCUrl(e.target.value)}
                placeholder="URL de l'API (optionnel) — https://api.exemple.com"
                className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <input
                type="password"
                value={cKey}
                onChange={(e) => setCKey(e.target.value)}
                placeholder="Clé API / jeton d'accès"
                className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div className="flex items-center justify-end gap-2">
              <button onClick={() => setCOpen(false)} className="rounded-lg px-3 py-2 text-xs text-muted-foreground hover:text-foreground">
                Annuler
              </button>
              <button
                onClick={addCustom}
                disabled={!cName.trim() || !cKey.trim() || cSaving}
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {cSaving ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Ajout…</> : 'Ajouter'}
              </button>
            </div>
            <p className="text-[11px] text-muted-foreground">
              L&apos;accès est enregistré de façon sécurisée pour votre compte. Indiquez ensuite à vos agents
              ce que vous souhaitez automatiser sur cette plateforme.
            </p>
          </div>
        )}

        {/* Liste des plateformes personnalisées */}
        {custom.length > 0 && (
          <div className="mt-4 space-y-2 border-t border-border pt-4">
            {custom.map((c) => (
              <div key={c.platform} className="flex items-center justify-between gap-3 rounded-lg border border-border p-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Check className="h-3.5 w-3.5 text-green-600" />
                    {c.name}
                    <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">{c.category}</span>
                  </div>
                  {c.baseUrl && <div className="truncate text-xs text-muted-foreground">{c.baseUrl}</div>}
                </div>
                <button onClick={() => disconnect(c.platform)} className="shrink-0 text-xs text-muted-foreground hover:text-destructive transition-colors">
                  Retirer
                </button>
              </div>
            ))}
          </div>
        )}
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
