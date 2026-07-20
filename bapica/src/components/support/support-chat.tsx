'use client'

import { useEffect, useRef, useState } from 'react'
import { LifeBuoy, X, Send, Loader2, ThumbsDown } from 'lucide-react'
import { supabase } from '@/lib/supabase'

interface Msg { role: 'user' | 'assistant'; content: string }

const SUGGESTIONS_CLIENT = [
  'Comment connecter WhatsApp ?',
  'Comment trouver des prospects ?',
  'À quoi sert « Actions à valider » ?',
  'Pourquoi je ne vois pas Claire ?',
]

const SUGGESTIONS_VISITEUR = [
  "Qu'est-ce que Bapica ?",
  'Que font les 10 agents ?',
  'Combien ça coûte ?',
  'Comment démarrer l’essai gratuit ?',
]

/**
 * Bulle d'aide flottante : assistant qui explique comment utiliser Bapica.
 * Distinct des agents métier — il répond sur le produit lui-même.
 */
export function SupportChat() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [isClient, setIsClient] = useState(false)
  const [feedbackDone, setFeedbackDone] = useState<Record<number, boolean>>({})
  const endRef = useRef<HTMLDivElement>(null)

  const sendFeedback = async (i: number) => {
    if (feedbackDone[i]) return
    setFeedbackDone((prev) => ({ ...prev, [i]: true }))
    try {
      const { data: { session } } = await supabase.auth.getSession()
      const question = messages[i - 1]?.content || ''
      await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${session?.access_token || ''}` },
        body: JSON.stringify({ content: `Réponse jugée insuffisante. Question : "${question}"`, context: messages[i]?.content?.slice(0, 300) }),
      })
    } catch { /* ignore */ }
  }

  useEffect(() => {
    if (open) endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open])

  // Adapte les suggestions selon visiteur / client connecté.
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setIsClient(Boolean(data.session)))
  }, [])

  const send = async (question?: string) => {
    const text = (question ?? input).trim()
    if (!text || loading) return
    setInput('')
    const next = [...messages, { role: 'user' as const, content: text }]
    setMessages(next)
    setLoading(true)
    try {
      const { data: { session } } = await supabase.auth.getSession()
      const res = await fetch('/api/support', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${session?.access_token || ''}` },
        body: JSON.stringify({ message: text, history: messages.slice(-6) }),
      })
      const data = await res.json()
      setMessages([
        ...next,
        { role: 'assistant', content: data.response || data.error || "Désolé, je n'ai pas pu répondre." },
      ])
    } catch {
      setMessages([...next, { role: 'assistant', content: 'Erreur de connexion. Réessayez dans un instant.' }])
    }
    setLoading(false)
  }

  return (
    <>
      {/* Bouton flottant */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          aria-label="Besoin d'aide ?"
          className="fixed bottom-5 right-5 z-40 inline-flex items-center gap-2 rounded-full bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground shadow-lg hover:bg-primary/90 transition-colors"
        >
          <LifeBuoy className="h-5 w-5" />
          <span className="hidden sm:inline">Aide</span>
        </button>
      )}

      {/* Panneau */}
      {open && (
        <div className="fixed bottom-5 right-5 z-40 flex h-[32rem] w-[min(24rem,calc(100vw-2.5rem))] flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-2xl">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="flex items-center gap-2">
              <LifeBuoy className="h-4 w-4 text-primary" />
              <div>
                <div className="text-sm font-semibold">Aide Bapica</div>
                <div className="text-[11px] text-muted-foreground">Comment utiliser la plateforme</div>
              </div>
            </div>
            <button onClick={() => setOpen(false)} aria-label="Fermer" className="text-muted-foreground hover:text-foreground">
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
            {messages.length === 0 && (
              <div>
                <p className="text-sm text-muted-foreground">
                  {isClient
                    ? 'Posez votre question sur Bapica : configuration, agents, connexions, problème rencontré…'
                    : 'Une question sur Bapica ? Ce que font les agents, les formules, comment démarrer…'}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {(isClient ? SUGGESTIONS_CLIENT : SUGGESTIONS_VISITEUR).map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className="rounded-full border border-border px-3 py-1.5 text-[11px] text-muted-foreground hover:border-primary hover:text-primary transition-colors"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, i) => (
              <div key={i} className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
                <div
                  className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                    m.role === 'user'
                      ? 'rounded-br-sm bg-primary text-primary-foreground'
                      : 'rounded-bl-sm bg-muted text-foreground'
                  }`}
                >
                  {m.content}
                </div>
                {m.role === 'assistant' && (
                  <button
                    onClick={() => sendFeedback(i)}
                    disabled={feedbackDone[i]}
                    className="mt-1 inline-flex items-center gap-1 text-[10px] text-muted-foreground hover:text-destructive disabled:text-green-600 disabled:hover:text-green-600 transition-colors"
                  >
                    <ThumbsDown className="h-3 w-3" />
                    {feedbackDone[i] ? 'Merci pour votre retour' : 'Pas utile'}
                  </button>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="rounded-2xl bg-muted px-3.5 py-2.5">
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          <div className="border-t border-border p-3">
            <div className="flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && send()}
                placeholder="Votre question…"
                className="min-w-0 flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <button
                onClick={() => send()}
                disabled={!input.trim() || loading}
                className="shrink-0 rounded-lg bg-primary px-3 py-2 text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
                aria-label="Envoyer"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
