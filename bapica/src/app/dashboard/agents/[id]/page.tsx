'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import { Send, User, ArrowLeft, Sparkles } from 'lucide-react'
import Link from 'next/link'
import { getAgentById } from '@/lib/agents'
import { AgentAvatar } from '@/components/agents/agent-avatar'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

export default function AgentChatPage() {
  const params = useParams()
  const agent = getAgentById(params.id as string)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  if (!agent) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-bold">Agent introuvable</h2>
          <p className="mt-2 text-muted-foreground">
            <Link href="/dashboard/agents" className="text-primary hover:underline">
              Retour à la liste
            </Link>
          </p>
        </div>
      </div>
    )
  }

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMessage = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }])
    setLoading(true)

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agentId: agent.id,
          message: userMessage,
          history: messages,
        }),
      })

      const data = await res.json()
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: data.response },
      ])
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Désolé, une erreur est survenue. Veuillez réessayer.' },
      ])
    }
    setLoading(false)
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      {/* Header */}
      <div className="flex items-center gap-4 border-b border-border pb-4">
        <Link
          href="/dashboard/agents"
          className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-muted transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <AgentAvatar agent={agent} size={44} className="shrink-0 rounded-full shadow-md" />
        <div>
          <div className="flex items-center gap-2">
            <h2 className="font-semibold">{agent.persona}</h2>
            <Sparkles className="h-4 w-4 text-primary" />
          </div>
          <p className="text-xs text-muted-foreground">
            {agent.name} • Modèle : {agent.model}
          </p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 space-y-4 overflow-y-auto py-4">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center">
            <div className="max-w-md text-center">
              <AgentAvatar agent={agent} size={72} className="mx-auto mb-4 rounded-full shadow-lg" />
              <h3 className="font-semibold">{agent.persona}</h3>
              <p className="text-sm text-muted-foreground">{agent.name}</p>
              <p className="mt-2 text-sm text-muted-foreground">
                {agent.description}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Outils : {agent.tools.join(', ')}
              </p>
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}
          >
            {msg.role === 'assistant' && (
              <AgentAvatar agent={agent} size={32} className="shrink-0 rounded-full" />
            )}
            <div
              className={`max-w-[80%] rounded-xl px-4 py-3 text-sm ${
                msg.role === 'user'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted'
              }`}
            >
              {msg.content}
            </div>
            {msg.role === 'user' && (
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted">
                <User className="h-4 w-4" />
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <AgentAvatar agent={agent} size={32} className="shrink-0 rounded-full" />
            <div className="rounded-xl bg-muted px-4 py-3">
              <div className="flex gap-1">
                <div className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40" />
                <div className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40" style={{ animationDelay: '0.1s' }} />
                <div className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40" style={{ animationDelay: '0.2s' }} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={sendMessage} className="flex gap-3 border-t border-border pt-4">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={`Posez votre question à ${agent.name}...`}
          className="flex-1 rounded-lg border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  )
}
