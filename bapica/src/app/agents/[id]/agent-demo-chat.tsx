'use client'

import { useState } from 'react'
import Link from 'next/link'
import type { AgentConfig } from '@/lib/agents'
import { Send, Loader2 } from 'lucide-react'

/**
 * Chat démo intégrable (3 messages, sans compte) — appelle /api/demo-chat.
 * Utilisé en bas de la page descriptive d'un agent.
 */
export default function AgentDemoChat({ agent }: { agent: AgentConfig }) {
  const [message, setMessage] = useState('')
  const [chat, setChat] = useState<Array<{ role: string; content: string }>>([])
  const [loading, setLoading] = useState(false)
  const [remaining, setRemaining] = useState(3)

  const handleSend = async () => {
    if (!message.trim() || loading || remaining <= 0) return
    setLoading(true)
    const userMsg = message.trim()
    setMessage('')
    setChat((prev) => [...prev, { role: 'user', content: userMsg }])

    try {
      const res = await fetch('/api/demo-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agentId: agent.id, message: userMsg }),
      })
      const data = await res.json()
      if (data.response) {
        setChat((prev) => [...prev, { role: 'assistant', content: data.response }])
        setRemaining(data.remaining ?? remaining - 1)
      } else {
        setChat((prev) => [...prev, { role: 'assistant', content: data.error || 'Le service est en cours de configuration. Réessayez bientôt.' }])
      }
    } catch {
      setChat((prev) => [...prev, { role: 'assistant', content: 'Désolé, une erreur est survenue.' }])
    }
    setLoading(false)
  }

  const initial = agent.persona?.[0] || '?'

  return (
    <div className="rounded-2xl border border-[#E5E7EB] bg-white overflow-hidden">
      {/* En-tête du chat */}
      <div className="flex items-center gap-3 border-b border-[#F3F4F6] bg-[#F9FAFB] px-5 py-4">
        <div
          className="flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold text-white"
          style={{ backgroundImage: `linear-gradient(135deg, ${agent.avatar.from}, ${agent.avatar.to})` }}
        >
          {initial}
        </div>
        <div>
          <div className="text-sm font-semibold text-[#111827]">Essayer {agent.persona}</div>
          <div className="text-xs text-[#6B7280]">Démo gratuite — {remaining} message{remaining > 1 ? 's' : ''} restant{remaining > 1 ? 's' : ''}</div>
        </div>
      </div>

      {/* Fil de conversation */}
      <div className="min-h-[220px] px-5 py-5">
        {chat.length === 0 ? (
          <p className="text-sm text-[#9CA3AF]">
            Posez une question à {agent.persona} pour voir comment cet agent répond.
          </p>
        ) : (
          <div className="space-y-4">
            {chat.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-[#111827] text-white rounded-br-sm'
                      : 'bg-[#F3F4F6] text-[#111827] rounded-bl-sm'
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="rounded-2xl bg-[#F3F4F6] px-4 py-3">
                  <Loader2 className="h-4 w-4 animate-spin text-[#6B7280]" />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Saisie */}
      <div className="border-t border-[#F3F4F6] bg-[#F9FAFB] px-5 py-4">
        {remaining <= 0 ? (
          <div className="text-center">
            <p className="mb-3 text-sm text-[#6B7280]">Démo terminée — créez votre compte pour continuer.</p>
            <Link
              href="/signup"
              className="inline-flex items-center rounded-lg bg-[#2563EB] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#1D4ED8] transition-colors"
            >
              Créer un compte gratuit
            </Link>
          </div>
        ) : (
          <div className="flex gap-3">
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder={`Parlez avec ${agent.persona}...`}
              className="flex-1 rounded-lg border border-[#E5E7EB] bg-white px-4 py-2.5 text-sm text-[#111827] focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
            />
            <button
              onClick={handleSend}
              disabled={!message.trim() || loading}
              className="rounded-lg bg-[#111827] px-4 py-2.5 text-white hover:bg-[#1F2937] disabled:opacity-50 transition-colors"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
