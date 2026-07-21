'use client'

import { useState } from 'react'
import Link from 'next/link'
import { supabase } from '@/lib/supabase'
import { Sparkles, Clapperboard, ArrowLeft, Wand2, MessagesSquare, ArrowRight } from 'lucide-react'
import type { ProductionPackage } from '@/lib/video/maya'
import { ProductionPackageView } from '@/components/agents/production-package'

const PLATFORMS = ['TikTok', 'Reels', 'Shorts', 'YouTube', 'Pub Meta', 'VSL']
const OBJECTIVES = ['Vente', 'Publicité', 'Storytelling', 'UGC', 'Formation']
const DURATIONS = ['15s', '30s', '60s', '90s']
const STYLES = ['UGC', 'Cinématique', 'Corporate', 'Dynamique']
const VOICES = ['Femme', 'Homme', 'Aucune (musique seule)']

export default function VideoStudioPage() {
  const [idea, setIdea] = useState('')
  const [platform, setPlatform] = useState('TikTok')
  const [objective, setObjective] = useState('Vente')
  const [duration, setDuration] = useState('30s')
  const [style, setStyle] = useState('UGC')
  const [voice, setVoice] = useState('Femme')
  const [avatar, setAvatar] = useState(false)

  const [phase, setPhase] = useState<'brief' | 'questions'>('brief')
  const [questions, setQuestions] = useState<string[]>([])
  const [answers, setAnswers] = useState<Record<number, string>>({})

  const [loading, setLoading] = useState(false)
  const [loadingMsg, setLoadingMsg] = useState('')
  const [error, setError] = useState('')
  const [pkg, setPkg] = useState<ProductionPackage | null>(null)

  const briefBody = () => ({
    idea, platform, objective, duration, style,
    voice: voice.startsWith('Aucune') ? 'aucune' : voice.toLowerCase(),
    avatar,
  })

  const token = async () => (await supabase.auth.getSession()).data.session?.access_token || ''

  // Étape 1 : Maya pose des questions de cadrage.
  const askQuestions = async () => {
    if (!idea.trim() || loading) return
    setLoading(true); setLoadingMsg('Maya prépare ses questions…'); setError(''); setPkg(null)
    try {
      const res = await fetch('/api/video/questions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
        body: JSON.stringify(briefBody()),
      })
      const data = await res.json()
      if (!res.ok || data.error) { setError(data.error || 'Erreur inattendue.'); setLoading(false); return }
      if (Array.isArray(data.questions) && data.questions.length > 0) {
        setQuestions(data.questions); setAnswers({}); setPhase('questions')
      } else {
        // Pas de questions → on génère directement.
        await generate()
        return
      }
    } catch {
      setError('Erreur de connexion. Réessayez.')
    }
    setLoading(false)
  }

  // Étape 2 : génération du storyboard (avec les réponses éventuelles).
  const generate = async () => {
    setLoading(true); setLoadingMsg('Maya conçoit votre storyboard…'); setError('')
    try {
      const clarifications = questions
        .map((q, i) => (answers[i]?.trim() ? `- ${q} → ${answers[i].trim()}` : ''))
        .filter(Boolean)
        .join('\n')
      const res = await fetch('/api/video/orchestrate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
        body: JSON.stringify({ ...briefBody(), clarifications }),
      })
      const data = await res.json()
      if (!res.ok || data.error) setError(data.error || 'Erreur inattendue.')
      else { setPkg(data.package); setPhase('brief') }
    } catch {
      setError('Erreur de connexion. Réessayez.')
    }
    setLoading(false)
  }

  return (
    <div>
      {/* En-tête */}
      <div className="reveal mb-8 flex items-center gap-3">
        <Link href="/dashboard" className="text-muted-foreground hover:text-foreground"><ArrowLeft className="h-5 w-5" /></Link>
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-pink-500 to-purple-600 text-white shadow-md">
          <Clapperboard className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-xl font-bold">Bapica Studio</h1>
          <p className="text-sm text-muted-foreground">par Maya — directrice créative IA</p>
        </div>
      </div>

      {/* Brief */}
      {phase === 'brief' && (
        <div className="card-elevated p-6">
          <label className="mb-1.5 block text-sm font-medium">Votre idée de vidéo</label>
          <textarea
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            rows={3}
            placeholder="Ex : une pub pour une montre connectée qui suit le sommeil, pour un public 25-40 ans qui veut mieux dormir."
            className="w-full resize-none rounded-xl border border-border bg-background px-4 py-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
          />

          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Select label="Plateforme" value={platform} onChange={setPlatform} options={PLATFORMS} />
            <Select label="Objectif" value={objective} onChange={setObjective} options={OBJECTIVES} />
            <Select label="Durée" value={duration} onChange={setDuration} options={DURATIONS} />
            <Select label="Style" value={style} onChange={setStyle} options={STYLES} />
            <Select label="Voix off" value={voice} onChange={setVoice} options={VOICES} />
            <label className="flex items-end gap-2 pb-2.5 text-sm">
              <input type="checkbox" checked={avatar} onChange={(e) => setAvatar(e.target.checked)} className="h-4 w-4 rounded border-border" />
              Présentateur qui parle (avatar)
            </label>
          </div>

          <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">Maya vous pose d&apos;abord quelques questions pour cerner le besoin, puis conçoit le storyboard.</p>
            <div className="flex items-center gap-2">
              <button
                onClick={generate}
                disabled={!idea.trim() || loading}
                className="rounded-lg border border-border px-4 py-2.5 text-sm font-medium hover:bg-muted disabled:opacity-50 transition-colors"
              >
                Générer directement
              </button>
              <button
                onClick={askQuestions}
                disabled={!idea.trim() || loading}
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-all"
              >
                {loading ? <><Sparkles className="h-4 w-4 animate-pulse" /> {loadingMsg || 'Maya réfléchit…'}</> : <><MessagesSquare className="h-4 w-4" /> Continuer avec Maya</>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Questions de cadrage */}
      {phase === 'questions' && (
        <div className="card-elevated p-6">
          <div className="mb-4 flex items-center gap-2">
            <MessagesSquare className="h-5 w-5 text-primary" />
            <h2 className="font-semibold">Quelques questions de Maya</h2>
          </div>
          <p className="mb-5 text-sm text-muted-foreground">Répondez à ce que vous voulez (les questions sont facultatives) — plus vous précisez, meilleur sera le storyboard.</p>
          <div className="space-y-4">
            {questions.map((q, i) => (
              <div key={i}>
                <label className="mb-1.5 block text-sm font-medium">{q}</label>
                <input
                  value={answers[i] || ''}
                  onChange={(e) => setAnswers((a) => ({ ...a, [i]: e.target.value }))}
                  placeholder="Votre réponse (facultatif)…"
                  className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            ))}
          </div>
          <div className="mt-6 flex items-center justify-between">
            <button onClick={() => setPhase('brief')} disabled={loading} className="inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium hover:bg-muted disabled:opacity-50 transition-colors">
              <ArrowLeft className="h-4 w-4" /> Modifier l&apos;idée
            </button>
            <button
              onClick={generate}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-all"
            >
              {loading ? <><Sparkles className="h-4 w-4 animate-pulse" /> {loadingMsg || 'Génération…'}</> : <><Wand2 className="h-4 w-4" /> Générer le storyboard <ArrowRight className="h-4 w-4" /></>}
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="mt-6 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{error}</div>
      )}

      {/* Résultat : package de production */}
      {pkg && <div className="mt-8"><ProductionPackageView pkg={pkg} /></div>}
    </div>
  )
}

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: string[] }) {
  return (
    <div>
      <label className="mb-1.5 block text-xs font-medium text-muted-foreground">{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary">
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  )
}
