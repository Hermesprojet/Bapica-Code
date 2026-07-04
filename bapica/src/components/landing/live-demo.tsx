'use client'

import { useState, useRef, useEffect } from 'react'
import Link from 'next/link'
import { Send, User, Sparkles, ArrowRight, Lock } from 'lucide-react'
import { getAgentById } from '@/lib/agents'
import { AgentAvatar } from '@/components/agents/agent-avatar'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const SUGGESTIONS = [
  'Comment trouver plus de clients pour mon activité ?',
  'Rédige un post LinkedIn pour présenter mon entreprise',
  'Comment relancer poliment une facture impayée ?',
]

const MAX_MESSAGES = 3

export function LiveDemo() {
  const leo = getAgentById('general')
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [limitReached, setLimitReached] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  const userCount = messages.filter((m) => m.role === 'user').length
  const remaining = Math.max(0, MAX_MESSAGES - userCount)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, loading])

  const send = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || loading || limitReached) return

    setInput('')
    const nextMessages: Message[] = [...messages, { role: 'user', content: trimmed }]
    setMessages(nextMessages)
    setLoading(true)

    try {
      const res = await fetch('/api/demo-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: trimmed, history: messages }),
      })
      const data = await res.json()

      if (data.limitReached) {
        setLimitReached(true)
      }
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.response || data.error || 'Désolé, une erreur est survenue. Réessayez.',
        },
      ])
      if (typeof data.remaining === 'number' && data.remaining <= 0) {
        setLimitReached(true)
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Désolé, une erreur est survenue. Réessayez.' },
      ])
    }
    setLoading(false)
  }

  if (!leo) return null

  return (
    <section id="demo" className="border-t border-border py-20 md:py-28">
      <div className="container mx-auto px-4">
        <div className="mx-auto mb-10 max-w-2xl text-center">
          <div className="mx-auto mb-4 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-sm">
            <Sparkles className="h-4 w-4 text-primary" />
            <span className="text-muted-foreground">Démo en direct · sans inscription</span>
          </div>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Essayez <span className="gradient-text">Léo</span> maintenant
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Posez une vraie question sur votre activité. {MAX_MESSAGES} messages gratuits, réponse en quelques secondes.
          </p>
        </div>

        <div className="mx-auto max-w-2xl overflow-hidden rounded-2xl border border-border bg-card shadow-lg">
          {/* En-tête du chat */}
          <div className="flex items-center gap-3 border-b border-border bg-muted/30 px-5 py-4">
            <AgentAvatar agent={leo} size={40} className="shrink-0 rounded-full shadow-sm" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold">{leo.persona}</p>
              <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                En ligne — Agent Général
              </p>
            </div>
            {!limitReached && userCount > 0 && (
              <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
                {remaining} message{remaining > 1 ? 's' : ''} restant{remaining > 1 ? 's' : ''}
              </span>
            )}
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="h-80 space-y-4 overflow-y-auto p-5">
            {messages.length === 0 && (
              <div className="flex h-full flex-col items-center justify-center gap-4">
                <p className="text-center text-sm text-muted-foreground">
                  Bonjour, je suis {leo.persona}. Posez-moi une question sur votre activité — ou choisissez un exemple :
                </p>
                <div className="flex flex-col gap-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className="rounded-lg border border-border bg-background px-4 py-2.5 text-left text-sm hover:border-primary/50 hover:bg-primary/5 transition-all"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                {msg.role === 'assistant' && (
                  <AgentAvatar agent={leo} size={30} className="mt-0.5 shrink-0 rounded-full" />
                )}
                <div
                  className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm leading-relaxed ${
                    msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'
                  }`}
                >
                  {msg.content}
                </div>
                {msg.role === 'user' && (
                  <div className="mt-0.5 flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-full bg-muted">
                    <User className="h-4 w-4" />
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex gap-3">
                <AgentAvatar agent={leo} size={30} className="mt-0.5 shrink-0 rounded-full" />
                <div className="rounded-xl bg-muted px-4 py-3">
                  <div className="flex gap-1">
                    <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40" style={{ animationDelay: '0.1s' }} />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40" style={{ animationDelay: '0.2s' }} />
                  </div>
                </div>
              </div>
            )}

            {limitReached && (
              <div className="rounded-xl border border-primary/30 bg-primary/5 p-5 text-center">
                <Lock className="mx-auto mb-2 h-5 w-5 text-primary" />
                <p className="text-sm font-semibold">Vous avez aimé l&apos;échange ?</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Créez un compte gratuit pour continuer avec Léo et débloquer tous les agents.
                </p>
                <Link
                  href="/signup"
                  className="mt-4 inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-6 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-all"
                >
                  Continuer gratuitement <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            )}
          </div>

          {/* Saisie */}
          <form
            onSubmit={(e) => {
              e.preventDefault()
              send(input)
            }}
            className="flex gap-2 border-t border-border p-4"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              maxLength={500}
              placeholder={
                limitReached
                  ? 'Créez un compte pour continuer...'
                  : `Écrivez votre question à ${leo.persona}...`
              }
              disabled={loading || limitReached}
              className="flex-1 rounded-lg border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={loading || limitReached || !input.trim()}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
        </div>

        <p className="mt-4 text-center text-xs text-muted-foreground">
          Démonstration limitée à {MAX_MESSAGES} messages. Aucune donnée personnelle requise.
        </p>
      </div>
    </section>
  )
}
