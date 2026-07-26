'use client'

// Bouton « Connecter WhatsApp » via Meta Embedded Signup.
// Le client garde SON numéro, sans Twilio ni Facebook Developers : une popup Meta s'ouvre,
// il se connecte à son compte Meta Business, autorise Bapica, et c'est fini.
//
// ÉCRIT À L'AVEUGLE (non testable sans app Meta validée). S'active dès que les variables
// NEXT_PUBLIC_FACEBOOK_APP_ID et NEXT_PUBLIC_WHATSAPP_CONFIG_ID sont présentes.

import { useEffect, useRef, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { MessageCircle, Loader2, Check, AlertCircle } from 'lucide-react'

const APP_ID = process.env.NEXT_PUBLIC_FACEBOOK_APP_ID || ''
const CONFIG_ID = process.env.NEXT_PUBLIC_WHATSAPP_CONFIG_ID || ''
const GRAPH_VERSION = 'v21.0'

/* eslint-disable @typescript-eslint/no-explicit-any */
export function WhatsAppEmbeddedButton({ onConnected }: { onConnected?: (info: { displayNumber?: string }) => void }) {
  const [ready, setReady] = useState(false)
  const [status, setStatus] = useState<'idle' | 'connecting' | 'ok' | 'err'>('idle')
  const [msg, setMsg] = useState('')
  // Données renvoyées par la popup Meta (phone_number_id, waba_id) avant le callback FB.login.
  const signup = useRef<{ phoneNumberId?: string; wabaId?: string }>({})

  const configured = !!APP_ID && !!CONFIG_ID

  // Charge le SDK Meta une seule fois + initialise FB, et écoute l'événement Embedded Signup.
  useEffect(() => {
    if (!configured) return
    const onMessage = (event: MessageEvent) => {
      if (!/facebook\.com$/.test(new URL(event.origin).hostname) && !event.origin.includes('facebook.com')) return
      try {
        const data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data
        if (data?.type === 'WA_EMBEDDED_SIGNUP') {
          signup.current = { phoneNumberId: data?.data?.phone_number_id, wabaId: data?.data?.waba_id }
        }
      } catch { /* message non-JSON : ignorer */ }
    }
    window.addEventListener('message', onMessage)

    const w = window as any
    if (w.FB) { setReady(true); return () => window.removeEventListener('message', onMessage) }

    w.fbAsyncInit = () => {
      w.FB.init({ appId: APP_ID, autoLogAppEvents: true, xfbml: false, version: GRAPH_VERSION })
      setReady(true)
    }
    if (!document.getElementById('facebook-jssdk')) {
      const s = document.createElement('script')
      s.id = 'facebook-jssdk'
      s.src = 'https://connect.facebook.net/en_US/sdk.js'
      s.async = true
      s.defer = true
      s.crossOrigin = 'anonymous'
      document.body.appendChild(s)
    }
    return () => window.removeEventListener('message', onMessage)
  }, [configured])

  const token = async () => (await supabase.auth.getSession()).data.session?.access_token || ''

  const launch = () => {
    const w = window as any
    if (!w.FB || status === 'connecting') return
    setStatus('connecting'); setMsg('')
    signup.current = {}

    w.FB.login(
      async (response: any) => {
        const code = response?.authResponse?.code
        if (!code) { setStatus('err'); setMsg('Connexion annulée.'); return }
        // Laisse le temps à l'événement Embedded Signup d'arriver, puis envoie au serveur.
        setTimeout(async () => {
          try {
            const res = await fetch('/api/channels/whatsapp/embedded', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
              body: JSON.stringify({ code, phoneNumberId: signup.current.phoneNumberId, wabaId: signup.current.wabaId }),
            })
            const data = await res.json()
            if (res.ok && data.success) {
              setStatus('ok'); setMsg(`WhatsApp connecté${data.displayNumber ? ` (${data.displayNumber})` : ''}.`)
              onConnected?.({ displayNumber: data.displayNumber })
            } else {
              setStatus('err'); setMsg(data.error || 'Échec de la connexion.')
            }
          } catch {
            setStatus('err'); setMsg('Erreur de connexion au serveur.')
          }
        }, 800)
      },
      { config_id: CONFIG_ID, response_type: 'code', override_default_response_type: true, extras: { setup: {}, sessionInfoVersion: '3' } },
    )
  }

  if (!configured) {
    return (
      <p className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
        <AlertCircle className="h-3.5 w-3.5" />
        Connexion Meta « gardez votre numéro » bientôt disponible (activation en cours côté Bapica).
      </p>
    )
  }

  return (
    <div>
      <button
        onClick={launch}
        disabled={!ready || status === 'connecting'}
        className="inline-flex items-center gap-2 rounded-lg bg-[#25D366] px-4 py-2 text-sm font-semibold text-white hover:bg-[#1FB855] disabled:opacity-50 transition-colors"
      >
        {status === 'connecting'
          ? <><Loader2 className="h-4 w-4 animate-spin" /> Connexion…</>
          : <><MessageCircle className="h-4 w-4" /> Connecter avec WhatsApp</>}
      </button>
      {msg && (
        <p className={`mt-2 inline-flex items-start gap-1.5 text-xs ${status === 'ok' ? 'text-green-600' : 'text-destructive'}`}>
          {status === 'ok' ? <Check className="mt-0.5 h-3.5 w-3.5 shrink-0" /> : <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />}
          <span className="break-words">{msg}</span>
        </p>
      )}
    </div>
  )
}
