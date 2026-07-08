'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import AGENTS from '@/lib/agents'
import { ArrowLeft, Bot, Send, Loader2 } from 'lucide-react'

export default function AgentPage({ params }: { params: { id: string } }) {
  const router = useRouter()
  const agent = AGENTS.find(a => a.id === params.id)
  const [message, setMessage] = useState('')
  const [chat, setChat] = useState<Array<{role: string, content: string}>>([])
  const [loading, setLoading] = useState(false)
  const [remaining, setRemaining] = useState(3)

  if (!agent) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <h1 className="text-3xl font-bold">Agent introuvable</h1>
          <Link href="/" className="mt-4 inline-block text-primary hover:underline">
            Retour à l&apos;accueil
          </Link>
        </div>
      </div>
    )
  }

  const handleSend = async () => {
    if (!message.trim() || loading || remaining <= 0) return
    setLoading(true)
    const userMsg = message.trim()
    setMessage('')
    setChat(prev => [...prev, { role: 'user', content: userMsg }])

    try {
      const res = await fetch('/api/demo-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agentId: agent.id, message: userMsg })
      })
      const data = await res.json()
      if (data.response) {
        setChat(prev => [...prev, { role: 'assistant', content: data.response }])
        setRemaining(data.remaining ?? remaining - 1)
      }
    } catch (e) {
      setChat(prev => [...prev, { role: 'assistant', content: 'Désolé, une erreur est survenue.' }])
    }
    setLoading(false)
  }

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Header */}
      <header className="border-b border-border">
        <div className="container mx-auto max-w-4xl flex items-center gap-4 px-4 h-14">
          <Link href="/" className="text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div className={`flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br ${agent.color || 'from-primary to-primary'} text-white text-sm font-bold`}>
            {agent.persona?.[0] || '?'}
          </div>
          <div>
            <h1 className="font-semibold text-sm">{agent.name}</h1>
            <p className="text-xs text-muted-foreground">{agent.persona} — {agent.description}</p>
          </div>
        </div>
      </header>

      {/* Chat */}
      <div className="flex-1 container mx-auto max-w-3xl px-4 py-6">
        {chat.length === 0 ? (
          <div className="text-center py-20">
            <div className={`inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br ${agent.color || 'from-primary to-primary'} text-white text-2xl font-bold mb-6 shadow-lg`}>
              {agent.persona?.[0] || '?'}
            </div>
            <h2 className="text-2xl font-bold">{agent.persona}</h2>
            <p className="mt-2 text-muted-foreground max-w-md mx-auto">
              {agent.description}
            </p>
            <p className="mt-1 text-sm text-muted-foreground/60">
              {agent.teamRole === 'coordinator' ? 'Coordinateur d\'équipe — supervise tous les agents' : agent.teamRole === 'analyst' ? 'Agent Analyste — analyse et reporting' : 'Agent Spécialiste'}
            </p>
            <p className="mt-4 text-xs text-muted-foreground/40">
              Démo gratuite — {remaining} messages restants
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {chat.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[80%] rounded-xl px-4 py-3 text-sm ${
                  msg.role === 'user'
                    ? 'bg-foreground text-background'
                    : 'bg-muted text-foreground'
                }`}>
                  {msg.content}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-muted rounded-xl px-4 py-3">
                  <Loader2 className="h-4 w-4 animate-spin" />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-border bg-card">
        <div className="container mx-auto max-w-3xl px-4 py-4">
          {remaining <= 0 ? (
            <div className="text-center">
              <p className="text-sm text-muted-foreground mb-3">
                Démo terminée — créez votre compte pour continuer
              </p>
              <Link href="/signup" className="btn-primary inline-flex">
                Créer un compte gratuit
              </Link>
            </div>
          ) : (
            <div className="flex gap-3">
              <input
                type="text"
                value={message}
                onChange={e => setMessage(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSend()}
                placeholder={`Parlez avec ${agent.persona}...`}
                className="flex-1 rounded-lg border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <button
                onClick={handleSend}
                disabled={!message.trim() || loading}
                className="rounded-lg bg-foreground text-background px-4 py-2.5 hover:bg-foreground/90 disabled:opacity-50 transition-colors"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
