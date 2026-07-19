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
    id: 'whatsapp',
    label: 'WhatsApp',
    icon: MessageCircle,
    color: 'text-[#25D366]',
    vars: ['WHATSAPP_TOKEN', 'WHATSAPP_PHONE_ID', 'WHATSAPP_VERIFY_TOKEN'],
    steps: [
      'Créez une app sur developers.facebook.com et ajoutez le produit « WhatsApp ».',
      'Récupérez le jeton d\'accès permanent et l\'identifiant du numéro (Phone number ID).',
      'Ajoutez WHATSAPP_TOKEN, WHATSAPP_PHONE_ID et WHATSAPP_VERIFY_TOKEN dans Vercel.',
      'Dans la configuration WhatsApp, déclarez l\'URL de webhook ci-dessous et le même verify token, puis abonnez-vous à l\'événement « messages ».',
    ],
  },
  {
    id: 'telegram',
    label: 'Telegram',
    icon: Send,
    color: 'text-[#0088CC]',
    vars: ['TELEGRAM_BOT_TOKEN'],
    steps: [
      'Ouvrez @BotFather sur Telegram et créez un bot avec /newbot.',
      'Copiez le jeton fourni et ajoutez-le dans Vercel sous TELEGRAM_BOT_TOKEN.',
      'Enregistrez le webhook en ouvrant dans un navigateur : https://api.telegram.org/bot<VOTRE_TOKEN>/setWebhook?url=<URL_WEBHOOK_CI_DESSOUS>',
    ],
  },
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

  // Connexion Telegram « en 1 clic »
  const [tgToken, setTgToken] = useState('')
  const [tgStatus, setTgStatus] = useState<'idle' | 'connecting' | 'ok' | 'err'>('idle')
  const [tgMsg, setTgMsg] = useState('')

  const token = async () => (await supabase.auth.getSession()).data.session?.access_token || ''

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
      setLoading(false)
    })()
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
      <div className="mb-8">
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

      {/* Connexion Telegram en 1 clic */}
      <div className="card-elevated mb-6 p-5">
        <div className="mb-1 flex items-center gap-2 text-sm font-semibold">
          <Send className="h-4 w-4 text-[#0088CC]" />
          Telegram — connexion en 1 clic
        </div>
        <p className="mb-3 text-xs text-muted-foreground">
          Créez un bot avec <span className="font-medium">@BotFather</span> (/newbot), copiez le jeton,
          collez-le ici : Bapica enregistre le webhook automatiquement (plus besoin de le faire à la main).
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
        <p className="mt-2 text-[11px] text-muted-foreground">
          Pour que le bot réponde, ajoutez aussi ce jeton comme <code className="rounded bg-muted px-1">TELEGRAM_BOT_TOKEN</code> dans Vercel (puis redéployez).
        </p>
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

      <p className="mt-6 text-xs text-muted-foreground">
        Les variables se configurent dans Vercel (Project Settings → Environment Variables), puis un
        redéploiement active le canal. Cette page ne lit jamais la valeur des jetons, seulement leur présence.
      </p>
    </div>
  )
}
