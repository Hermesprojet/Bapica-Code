'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { Check, Loader2, MessageCircle, Send, Facebook, AlertCircle, Copy } from 'lucide-react'

type ChannelId = 'whatsapp' | 'telegram' | 'messenger'

interface StatusResponse {
  channels: Record<ChannelId, boolean>
  webhookUrl: string | null
  appUrlConfigured: boolean
}

const CHANNELS: {
  id: ChannelId
  label: string
  icon: typeof MessageCircle
  color: string
  vars: string[]
  steps: string[]
}[] = [
  {
    id: 'messenger',
    label: 'Messenger',
    icon: Facebook,
    color: 'text-[#006AFF]',
    vars: ['MESSENGER_PAGE_TOKEN', 'MESSENGER_VERIFY_TOKEN'],
    steps: [
      'Dans votre app Meta, ajoutez le produit « Messenger » et liez votre Page Facebook.',
      'Générez le jeton de la Page et ajoutez MESSENGER_PAGE_TOKEN + MESSENGER_VERIFY_TOKEN dans Vercel.',
      'Déclarez l\'URL de webhook ci-dessous avec le même verify token, puis abonnez-vous à l\'événement « messages ».',
    ],
  },
]

export default function ChannelsPage() {
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState(false)

  // Connexion Telegram « en 1 clic » (multi-client)
  const [tgToken, setTgToken] = useState('')
  const [tgStatus, setTgStatus] = useState<'idle' | 'connecting' | 'ok' | 'err'>('idle')
  const [tgMsg, setTgMsg] = useState('')
  const [tgConn, setTgConn] = useState<{ connected: boolean; botUsername: string; needsSetup?: boolean } | null>(null)

  // Connexion WhatsApp (via Twilio) — in-app, sans Vercel
  const [waSid, setWaSid] = useState('')
  const [waAuth, setWaAuth] = useState('')
  const [waFrom, setWaFrom] = useState('')
  const [waConnStatus, setWaConnStatus] = useState<'idle' | 'connecting' | 'ok' | 'err'>('idle')
  const [waConnMsg, setWaConnMsg] = useState('')
  const [waConn, setWaConn] = useState<{ connected: boolean; fromNumber: string; needsSetup?: boolean } | null>(null)

  const token = async () => (await supabase.auth.getSession()).data.session?.access_token || ''

  const loadWhatsApp = async () => {
    try {
      const res = await fetch('/api/channels/whatsapp/connect', { headers: { Authorization: `Bearer ${await token()}` } })
      if (res.ok) setWaConn(await res.json())
    } catch { /* ignore */ }
  }

  const connectWhatsApp = async () => {
    if (!waSid.trim() || !waAuth.trim() || !waFrom.trim() || waConnStatus === 'connecting') return
    setWaConnStatus('connecting'); setWaConnMsg('')
    try {
      const res = await fetch('/api/channels/whatsapp/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
        body: JSON.stringify({ accountSid: waSid.trim(), authToken: waAuth.trim(), fromNumber: waFrom.trim() }),
      })
      const data = await res.json()
      if (res.ok && data.success) {
        setWaConnStatus('ok'); setWaConnMsg('WhatsApp connecté. Collez l’URL de webhook ci-dessus dans Twilio, et c’est prêt.')
        setWaSid(''); setWaAuth(''); setWaFrom('')
        setWaConn({ connected: true, fromNumber: data.fromNumber })
      } else {
        setWaConnStatus('err'); setWaConnMsg(data.error || 'Échec de la connexion.')
      }
    } catch {
      setWaConnStatus('err'); setWaConnMsg('Erreur de connexion.')
    }
  }

  const disconnectWhatsApp = async () => {
    setWaConnStatus('idle'); setWaConnMsg('')
    try {
      await fetch('/api/channels/whatsapp/connect', { method: 'DELETE', headers: { Authorization: `Bearer ${await token()}` } })
    } catch { /* ignore */ }
    setWaConn({ connected: false, fromNumber: '' })
  }

  const loadTelegram = async () => {
    try {
      const res = await fetch('/api/channels/telegram/connect', { headers: { Authorization: `Bearer ${await token()}` } })
      if (res.ok) setTgConn(await res.json())
    } catch { /* ignore */ }
  }

  // Test d'envoi WhatsApp (affiche l'erreur exacte de Twilio)
  const [waTo, setWaTo] = useState('')
  const [waStatus, setWaStatus] = useState<'idle' | 'sending' | 'ok' | 'err'>('idle')
  const [waMsg, setWaMsg] = useState('')

  const testWhatsApp = async () => {
    if (!waTo.trim() || waStatus === 'sending') return
    setWaStatus('sending'); setWaMsg('')
    try {
      const res = await fetch('/api/channels/whatsapp/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
        body: JSON.stringify({ to: waTo.trim() }),
      })
      const data = await res.json()
      if (res.ok && data.ok) {
        setWaStatus('ok'); setWaMsg('Message envoyé — regardez votre WhatsApp.')
      } else {
        setWaStatus('err'); setWaMsg(data.error || `Échec (HTTP ${res.status}).`)
      }
    } catch {
      setWaStatus('err'); setWaMsg('Erreur de connexion.')
    }
  }

  const disconnectTelegram = async () => {
    setTgStatus('idle'); setTgMsg('')
    try {
      await fetch('/api/channels/telegram/connect', { method: 'DELETE', headers: { Authorization: `Bearer ${await token()}` } })
    } catch { /* ignore */ }
    setTgConn({ connected: false, botUsername: '' })
  }

  const connectTelegram = async () => {
    if (!tgToken.trim() || tgStatus === 'connecting') return
    setTgStatus('connecting'); setTgMsg('')
    try {
      const res = await fetch('/api/channels/telegram/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
        body: JSON.stringify({ token: tgToken.trim() }),
      })
      const data = await res.json()
      if (res.ok && data.success) {
        setTgStatus('ok')
        setTgMsg(`Bot @${data.botUsername} connecté — webhook enregistré automatiquement.`)
        setTgToken('')
        setTgConn({ connected: true, botUsername: data.botUsername })
      } else {
        setTgStatus('err'); setTgMsg(data.error || 'Échec de la connexion.')
      }
    } catch {
      setTgStatus('err'); setTgMsg('Erreur de connexion.')
    }
  }

  useEffect(() => {
    ;(async () => {
      try {
        const res = await fetch('/api/channels/status', { headers: { Authorization: `Bearer ${await token()}` } })
        if (res.ok) setStatus(await res.json())
      } catch {
        /* ignore */
      }
      await loadTelegram()
      await loadWhatsApp()
      setLoading(false)
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const webhookUrl = status?.webhookUrl || 'https://<votre-app>/api/webhooks/messaging'

  const copyWebhook = async () => {
    try {
      await navigator.clipboard.writeText(webhookUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* ignore */
    }
  }

  return (
    <div>
      <div className="reveal mb-8">
        <h1 className="text-2xl font-bold">Canaux de messagerie</h1>
        <p className="mt-1 text-muted-foreground">
          Rendez vos agents joignables sur WhatsApp, Telegram et Messenger. Un seul webhook route
          automatiquement chaque message vers le bon agent.
        </p>
      </div>

      {/* URL de webhook commune */}
      <div className="card-elevated mb-6 p-5">
        <div className="mb-2 text-sm font-semibold">URL de webhook (commune aux 3 canaux)</div>
        <div className="flex flex-wrap items-center gap-3">
          <code className="flex-1 min-w-0 truncate rounded-lg border border-border bg-muted px-3 py-2 text-xs">{webhookUrl}</code>
          <button
            onClick={copyWebhook}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs font-medium hover:bg-muted transition-colors"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-green-600" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? 'Copié' : 'Copier'}
          </button>
        </div>
        {status && !status.appUrlConfigured && (
          <p className="mt-2 inline-flex items-center gap-1.5 text-xs text-amber-600">
            <AlertCircle className="h-3.5 w-3.5" />
            Ajoutez la variable NEXT_PUBLIC_APP_URL dans Vercel pour que le webhook fonctionne.
          </p>
        )}
      </div>

      {/* Connexion WhatsApp (via Twilio) — in-app, sans Vercel */}
      <div className="card-elevated mb-6 p-5">
        <div className="mb-1 flex items-center gap-2 text-sm font-semibold">
          <MessageCircle className="h-4 w-4 text-[#25D366]" />
          WhatsApp — connexion en 1 clic (via Twilio)
        </div>

        {waConn?.needsSetup ? (
          <p className="mt-2 inline-flex items-center gap-1.5 text-xs text-amber-600">
            <AlertCircle className="h-3.5 w-3.5" />
            Base non initialisée : exécutez <code className="rounded bg-muted px-1">supabase-schema.sql</code> dans Supabase, puis rechargez.
          </p>
        ) : waConn?.connected ? (
          <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
            <span className="inline-flex items-center gap-1.5 text-sm text-green-600">
              <Check className="h-4 w-4" />
              WhatsApp connecté{waConn.fromNumber ? ` (${waConn.fromNumber})` : ''} — vos agents répondent via votre compte Twilio.
            </span>
            <button
              onClick={disconnectWhatsApp}
              className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-destructive transition-colors"
            >
              Déconnecter
            </button>
          </div>
        ) : (
          <>
            <p className="mb-3 text-xs text-muted-foreground">
              Créez un compte gratuit sur <span className="font-medium">twilio.com</span> et activez WhatsApp
              (Messaging → « Try it out »). Copiez votre <span className="font-medium">Account SID</span>,
              votre <span className="font-medium">Auth Token</span> et votre <span className="font-medium">numéro WhatsApp</span>,
              collez-les ici : Bapica valide et active la connexion. <span className="font-medium">Rien à installer, rien dans Vercel.</span>
              &nbsp;Dernière étape : dans Twilio, collez l’URL de webhook ci-dessus dans « When a message comes in ».
            </p>
            <div className="grid gap-3 sm:grid-cols-3">
              <input
                type="text" value={waSid} onChange={(e) => setWaSid(e.target.value)}
                placeholder="Account SID (AC…)"
                className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <input
                type="password" value={waAuth} onChange={(e) => setWaAuth(e.target.value)}
                placeholder="Auth Token"
                className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <input
                type="tel" value={waFrom} onChange={(e) => setWaFrom(e.target.value)}
                placeholder="Numéro WhatsApp (+14155238886)"
                className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <button
              onClick={connectWhatsApp}
              disabled={!waSid.trim() || !waAuth.trim() || !waFrom.trim() || waConnStatus === 'connecting'}
              className="mt-3 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {waConnStatus === 'connecting' ? <><Loader2 className="h-4 w-4 animate-spin" /> Connexion…</> : <><MessageCircle className="h-4 w-4" /> Connecter WhatsApp</>}
            </button>
            {waConnMsg && (
              <p className={`mt-2 inline-flex items-start gap-1.5 text-xs ${waConnStatus === 'ok' ? 'text-green-600' : 'text-destructive'}`}>
                {waConnStatus === 'ok' ? <Check className="mt-0.5 h-3.5 w-3.5 shrink-0" /> : <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />}
                <span className="break-words">{waConnMsg}</span>
              </p>
            )}
          </>
        )}
      </div>

      {/* Connexion Telegram en 1 clic (multi-client) */}
      <div className="card-elevated mb-6 p-5">
        <div className="mb-1 flex items-center gap-2 text-sm font-semibold">
          <Send className="h-4 w-4 text-[#0088CC]" />
          Telegram — connexion en 1 clic
        </div>

        {tgConn?.needsSetup ? (
          <p className="mt-2 inline-flex items-center gap-1.5 text-xs text-amber-600">
            <AlertCircle className="h-3.5 w-3.5" />
            Base non initialisée : exécutez <code className="rounded bg-muted px-1">supabase-schema.sql</code> dans Supabase, puis rechargez.
          </p>
        ) : tgConn?.connected ? (
          <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
            <span className="inline-flex items-center gap-1.5 text-sm text-green-600">
              <Check className="h-4 w-4" />
              Bot {tgConn.botUsername ? `@${tgConn.botUsername}` : ''} connecté — le bot répond via le jeton enregistré.
            </span>
            <button
              onClick={disconnectTelegram}
              className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-destructive transition-colors"
            >
              Déconnecter
            </button>
          </div>
        ) : (
          <>
            <p className="mb-3 text-xs text-muted-foreground">
              Créez un bot avec <span className="font-medium">@BotFather</span> (/newbot), copiez le jeton,
              collez-le ici : Bapica valide le bot, enregistre le webhook et le rend actif. Rien à mettre dans Vercel.
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <input
                type="text"
                value={tgToken}
                onChange={(e) => setTgToken(e.target.value)}
                placeholder="Jeton BotFather (ex : 123456789:AA...)"
                className="flex-1 min-w-[220px] rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <button
                onClick={connectTelegram}
                disabled={!tgToken.trim() || tgStatus === 'connecting'}
                className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                {tgStatus === 'connecting' ? <><Loader2 className="h-4 w-4 animate-spin" /> Connexion…</> : <><Send className="h-4 w-4" /> Connecter</>}
              </button>
            </div>
            {tgMsg && (
              <p className={`mt-2 inline-flex items-center gap-1.5 text-xs ${tgStatus === 'ok' ? 'text-green-600' : 'text-destructive'}`}>
                {tgStatus === 'ok' ? <Check className="h-3.5 w-3.5" /> : <AlertCircle className="h-3.5 w-3.5" />}
                {tgMsg}
              </p>
            )}
          </>
        )}
      </div>

      {/* Cartes par canal */}
      <div className="space-y-4">
        {CHANNELS.map((c) => {
          const Icon = c.icon
          const configured = status?.channels?.[c.id] ?? false
          return (
            <div key={c.id} className="card-professional p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <Icon className={`h-6 w-6 ${c.color}`} />
                  <div className="font-semibold">{c.label}</div>
                </div>
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                ) : configured ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-green-500/10 px-3 py-1 text-xs font-medium text-green-700">
                    <Check className="h-3.5 w-3.5" /> Configuré
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-3 py-1 text-xs font-medium text-muted-foreground">
                    Non configuré
                  </span>
                )}
              </div>

              <ol className="mb-4 space-y-2">
                {c.steps.map((step, i) => (
                  <li key={i} className="flex gap-3 text-sm text-muted-foreground">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[11px] font-semibold text-primary">
                      {i + 1}
                    </span>
                    <span className="break-words">{step}</span>
                  </li>
                ))}
              </ol>

              <div className="flex flex-wrap gap-2">
                {c.vars.map((v) => (
                  <code key={v} className="rounded-md border border-border bg-muted px-2 py-1 text-[11px]">{v}</code>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {/* Diagnostic : test d'envoi WhatsApp */}
      <div className="card-elevated mt-6 p-5">
        <div className="mb-1 flex items-center gap-2 text-sm font-semibold">
          <MessageCircle className="h-4 w-4 text-[#25D366]" />
          Tester l&apos;envoi WhatsApp
        </div>
        <p className="mb-3 text-xs text-muted-foreground">
          Envoie un message de test via Twilio et affiche <span className="font-medium">l&apos;erreur exacte</span> en
          cas d&apos;échec. Le numéro doit avoir rejoint le sandbox Twilio (message « join … »).
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="tel"
            value={waTo}
            onChange={(e) => setWaTo(e.target.value)}
            placeholder="Votre numéro WhatsApp (ex : +32465474183)"
            className="flex-1 min-w-[220px] rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <button
            onClick={testWhatsApp}
            disabled={!waTo.trim() || waStatus === 'sending'}
            className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {waStatus === 'sending' ? <><Loader2 className="h-4 w-4 animate-spin" /> Envoi…</> : <><Send className="h-4 w-4" /> Envoyer un test</>}
          </button>
        </div>
        {waMsg && (
          <p className={`mt-2 flex items-start gap-1.5 text-xs ${waStatus === 'ok' ? 'text-green-600' : 'text-destructive'}`}>
            {waStatus === 'ok' ? <Check className="mt-0.5 h-3.5 w-3.5 shrink-0" /> : <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />}
            <span className="break-all">{waMsg}</span>
          </p>
        )}
      </div>

      <p className="mt-6 text-xs text-muted-foreground">
        WhatsApp et Telegram se connectent directement ici, sans rien installer ni toucher à Vercel.
        Seul Messenger nécessite encore une configuration côté serveur. Vos identifiants sont stockés de
        façon sécurisée et ne sont jamais réaffichés.
      </p>
    </div>
  )
}
