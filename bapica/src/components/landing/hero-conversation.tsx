'use client'

import { useEffect, useState } from 'react'

type Msg =
  | { side: 'user'; text: string }
  | { side: 'agent'; name: string; role: string; initial: string; color: string; text: string }

const MESSAGES: Msg[] = [
  { side: 'user', text: "Un client n'a toujours pas réglé sa facture de mars." },
  {
    side: 'agent',
    name: 'Claire',
    role: 'Comptabilité',
    initial: 'C',
    color: 'from-emerald-500 to-teal-600',
    text: "C'est parti — relance amiable envoyée par email (facture #2024‑089, 1 240 €). Je relance à J+7 si pas de réponse.",
  },
  { side: 'user', text: "Parfait. Trouve-moi aussi 3 prospects dans le BTP à Lyon." },
  {
    side: 'agent',
    name: 'Marc',
    role: 'Prospection',
    initial: 'M',
    color: 'from-blue-500 to-indigo-600',
    text: '3 entreprises qualifiées identifiées. Séquence de contact prête (email + LinkedIn) — je lance ?',
  },
]

export function HeroConversation() {
  const [visible, setVisible] = useState(0)
  const [typing, setTyping] = useState(false)

  useEffect(() => {
    let cancelled = false
    const timeouts: ReturnType<typeof setTimeout>[] = []
    const at = (ms: number, fn: () => void) => timeouts.push(setTimeout(() => { if (!cancelled) fn() }, ms))

    function run() {
      setVisible(0)
      setTyping(false)
      let t = 600
      MESSAGES.forEach((m, i) => {
        if (m.side === 'agent') {
          at(t, () => setTyping(true))
          t += 1300
          at(t, () => { setTyping(false); setVisible(i + 1) })
          t += 600
        } else {
          at(t, () => setVisible(i + 1))
          t += 1100
        }
      })
      t += 3000
      at(t, run) // boucle
    }
    run()
    return () => { cancelled = true; timeouts.forEach(clearTimeout) }
  }, [])

  return (
    <div className="relative">
      {/* Halo doux derrière la carte */}
      <div className="pointer-events-none absolute -inset-6 -z-10">
        <div className="absolute right-4 top-8 h-64 w-64 rounded-full bg-[#2563EB]/10 blur-3xl" />
        <div className="absolute left-0 bottom-4 h-56 w-56 rounded-full bg-teal-400/10 blur-3xl" />
      </div>

      <div className="rounded-2xl border border-[#E5E7EB] bg-white shadow-[0_24px_60px_-20px_rgba(15,23,42,0.25)] overflow-hidden">
        {/* En-tête */}
        <div className="flex items-center gap-3 border-b border-[#F3F4F6] px-5 py-3.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#2563EB] text-sm font-bold text-white">B</div>
          <div className="flex-1">
            <div className="text-sm font-semibold text-[#111827]">Bapica</div>
            <div className="flex items-center gap-1.5 text-xs text-[#10B981]">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-[#10B981]" />
              Vos agents sont en ligne
            </div>
          </div>
        </div>

        {/* Fil de conversation */}
        <div className="flex min-h-[340px] flex-col gap-4 px-5 py-6">
          {MESSAGES.slice(0, visible).map((m, i) =>
            m.side === 'user' ? (
              <div key={i} className="flex justify-end animate-slide-up">
                <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-[#111827] px-4 py-2.5 text-sm text-white">
                  {m.text}
                </div>
              </div>
            ) : (
              <div key={i} className="flex flex-col items-start gap-1 animate-slide-up">
                <div className="flex items-center gap-1.5 pl-1">
                  <div className={`flex h-5 w-5 items-center justify-center rounded-md bg-gradient-to-br ${m.color} text-[10px] font-bold text-white`}>
                    {m.initial}
                  </div>
                  <span className="text-xs font-medium text-[#374151]">{m.name}</span>
                  <span className="text-xs text-[#9CA3AF]">· {m.role}</span>
                </div>
                <div className="max-w-[85%] rounded-2xl rounded-bl-sm bg-[#F3F4F6] px-4 py-2.5 text-sm text-[#111827]">
                  {m.text}
                </div>
              </div>
            )
          )}

          {typing && (
            <div className="flex items-center gap-1.5 pl-1 animate-fade-in">
              <div className="flex gap-1 rounded-2xl rounded-bl-sm bg-[#F3F4F6] px-4 py-3">
                <span className="h-2 w-2 rounded-full bg-[#9CA3AF] animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="h-2 w-2 rounded-full bg-[#9CA3AF] animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="h-2 w-2 rounded-full bg-[#9CA3AF] animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
