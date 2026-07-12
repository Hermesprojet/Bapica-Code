'use client'

import { useState } from 'react'
import { Image, Video, Sparkles, Wand2, Play, Download, Clock } from 'lucide-react'
import Link from 'next/link'

type Mode = 'image' | 'video' | 'reel' | 'motion'

export default function VideoStudioPage() {
  const [mode, setMode] = useState<Mode>('image')
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')

  const modes: { id: Mode; label: string; icon: any; desc: string }[] = [
    { id: 'image', label: 'Image', icon: Image, desc: 'Texte → Image ultra-réaliste' },
    { id: 'video', label: 'Vidéo', icon: Video, desc: 'Texte → Clip vidéo court' },
    { id: 'reel', label: 'Reel', icon: Play, desc: 'Script → Reel vertical (TikTok/Reels)' },
    { id: 'motion', label: 'Motion', icon: Wand2, desc: 'Image → Animation cinématique' },
  ]

  const handleGenerate = async () => {
    if (!prompt.trim()) return
    setLoading(true)
    setError('')
    setResult(null)

    try {
      const res = await fetch('/api/video/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, prompt, style: 'professional', duration: 5 }),
      })
      const data = await res.json()
      if (data.error) setError(data.error)
      else setResult(data)
    } catch {
      setError('Erreur de connexion. Réessayez.')
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen bg-[#111] text-white">
      {/* Header */}
      <header className="border-b border-white/10 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center gap-6">
          <Link href="/dashboard" className="text-xl font-bold text-purple-400">Bapica Studio</Link>
          <span className="text-sm text-gray-500">par Maya · Créateur Vidéo IA</span>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-12">
        {/* Hero */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold mb-3">Créez des visuels percutants en quelques secondes.</h1>
          <p className="text-gray-400 text-lg">Un studio IA complet pour générer images, vidéos et Reels — sans équipe, sans matériel.</p>
        </div>

        {/* Mode selector */}
        <div className="grid grid-cols-4 gap-3 mb-10">
          {modes.map((m) => (
            <button
              key={m.id}
              onClick={() => { setMode(m.id); setResult(null) }}
              className={`p-4 rounded-xl border text-left transition-all ${
                mode === m.id
                  ? 'border-purple-500 bg-purple-500/10'
                  : 'border-white/10 hover:border-white/30 bg-white/5'
              }`}
            >
              <m.icon className="w-5 h-5 mb-2 text-purple-400" />
              <div className="font-semibold text-sm">{m.label}</div>
              <div className="text-xs text-gray-500 mt-1">{m.desc}</div>
            </button>
          ))}
        </div>

        {/* Prompt input */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-6 mb-8">
          <label className="block text-sm font-medium text-gray-300 mb-3">
            {mode === 'image' && 'Décrivez l\'image que vous voulez créer'}
            {mode === 'video' && 'Décrivez la vidéo que vous imaginez'}
            {mode === 'reel' && 'Écrivez votre script pour le Reel'}
            {mode === 'motion' && 'Décrivez la scène à animer'}
          </label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={
              mode === 'image' ? 'Un bureau moderne minimaliste, lumière naturelle, style Apple...' :
              mode === 'video' ? 'Un chef cuisinier qui prépare un plat signature, travelling lent, lumière chaude...' :
              mode === 'reel' ? 'Bonjour ! Aujourd\'hui je vous montre comment doubler votre productivité en 3 étapes simples...' :
              'Une skyline de Paris au coucher du soleil, caméra qui avance lentement vers la Tour Eiffel...'
            }
            className="w-full px-4 py-4 rounded-xl bg-black/50 border border-white/10 text-white placeholder:text-gray-600 resize-none focus:outline-none focus:border-purple-500 text-sm"
            rows={4}
          />
          <div className="flex items-center justify-between mt-4">
            <span className="text-xs text-gray-600">{prompt.length} / 500 caractères</span>
            <button
              onClick={handleGenerate}
              disabled={!prompt.trim() || loading}
              className="inline-flex items-center gap-2 px-6 py-2.5 bg-purple-600 text-white rounded-full font-semibold text-sm hover:bg-purple-500 disabled:opacity-40 transition-all"
            >
              {loading ? (
                <>
                  <Sparkles className="w-4 h-4 animate-pulse" />
                  Génération...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  Générer
                </>
              )}
            </button>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-8 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Result */}
        {result && result.success && (
          <div className="bg-white/5 border border-white/10 rounded-2xl p-8 text-center">
            {result.status === 'generating' ? (
              <div className="space-y-4">
                <div className="inline-flex items-center gap-3 text-purple-400">
                  <Sparkles className="w-6 h-6 animate-pulse" />
                  <span className="font-semibold">Génération en cours...</span>
                </div>
                <p className="text-gray-400">{result.message}</p>
                <p className="text-sm text-gray-600 flex items-center justify-center gap-2">
                  <Clock className="w-4 h-4" />
                  Temps estimé : {result.estimatedTime}
                </p>
                {result.provider && (
                  <p className="text-xs text-gray-600">Propulsé par {result.provider}</p>
                )}
              </div>
            ) : result.url ? (
              <div className="space-y-6">
                <img src={result.url} alt="Generated" className="max-w-full rounded-xl mx-auto" style={{ maxHeight: 500 }} />
                <div className="flex items-center justify-center gap-3">
                  <a href={result.url} download className="inline-flex items-center gap-2 px-4 py-2 bg-white/10 rounded-lg text-sm hover:bg-white/20 transition-colors">
                    <Download className="w-4 h-4" /> Télécharger
                  </a>
                </div>
              </div>
            ) : null}
          </div>
        )}

        {/* Features grid */}
        <div className="grid grid-cols-3 gap-4 mt-16 pt-12 border-t border-white/10">
          {[
            { title: 'Ultra-réaliste', desc: 'Images et vidéos photoréalistes générées par les meilleurs modèles IA.' },
            { title: 'Export direct', desc: 'Formats optimisés pour TikTok, Reels, Shorts et tous les réseaux.' },
            { title: 'Sans limites', desc: 'Créez autant de contenus que vous voulez. Pas de crédits, pas de quotas.' },
          ].map((f, i) => (
            <div key={i} className="text-center p-6">
              <div className="font-semibold mb-2">{f.title}</div>
              <p className="text-sm text-gray-500">{f.desc}</p>
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}
