'use client'

import { useState } from 'react'
import { Video, Loader2, CheckCircle, AlertCircle, Sparkles } from 'lucide-react'

const languages = [
  { code: 'fr', label: 'Français' },
  { code: 'en', label: 'English' },
  { code: 'ar', label: 'العربية' },
]

const videoFormats = [
  { id: 'landscape', label: '16:9 YouTube', w: 1920, h: 1080 },
  { id: 'portrait', label: '9:16 TikTok/Reels', w: 1080, h: 1920 },
  { id: 'square', label: '1:1 Instagram', w: 1080, h: 1080 },
]

export function VideoGeneratorForm() {
  const [script, setScript] = useState('')
  const [language, setLanguage] = useState('fr')
  const [format, setFormat] = useState('landscape')
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState<'idle' | 'generating' | 'done' | 'error'>('idle')
  const [videoUrl, setVideoUrl] = useState('')

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setStatus('generating')

    try {
      const res = await fetch('/api/video/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script,
          language,
          aspect_ratio: videoFormats.find((f) => f.id === format)?.id,
          title: 'Vidéo promotionnelle',
        }),
      })
      const data = await res.json()
      if (data.success) {
        setStatus('done')
        setVideoUrl(data.videoId)
      } else {
        setStatus('error')
      }
    } catch {
      setStatus('error')
    }
    setLoading(false)
  }

  return (
    <div className="rounded-xl border border-border bg-card p-6">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-pink-500 to-pink-600 text-white shadow-lg">
          <Video className="h-6 w-6" />
        </div>
        <div>
          <h2 className="font-semibold">Créateur Vidéo IA</h2>
          <p className="text-sm text-muted-foreground">Générez des vidéos avec avatar IA parlant</p>
        </div>
      </div>

      <form onSubmit={handleGenerate} className="space-y-4">
        {/* Script */}
        <div>
          <label className="block text-sm font-medium mb-1.5">Script de la vidéo</label>
          <textarea
            value={script}
            onChange={(e) => setScript(e.target.value)}
            rows={6}
            className="w-full rounded-lg border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none"
            placeholder="Rédigez le script de votre vidéo ici...
L'accroche (3 premières secondes) est cruciale.
Incluez un call-to-action à la fin."
            required
          />
        </div>

        {/* Options */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1.5">Langue</label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              {languages.map((l) => (
                <option key={l.code} value={l.code}>{l.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1.5">Format</label>
            <select
              value={format}
              onChange={(e) => setFormat(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              {videoFormats.map((f) => (
                <option key={f.id} value={f.id}>{f.label} ({f.w}x{f.h})</option>
              ))}
            </select>
          </div>
        </div>

        {/* Status */}
        {status === 'generating' && (
          <div className="flex items-center gap-3 rounded-lg bg-primary/10 p-4 text-sm">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <span>Génération en cours... (environ 2 minutes)</span>
          </div>
        )}
        {status === 'done' && (
          <div className="flex items-center gap-3 rounded-lg bg-green-500/10 p-4 text-sm text-green-600">
            <CheckCircle className="h-5 w-5" />
            <span>Vidéo générée ! ID : {videoUrl}</span>
          </div>
        )}
        {status === 'error' && (
          <div className="flex items-center gap-3 rounded-lg bg-destructive/10 p-4 text-sm text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span>Erreur lors de la génération. Vérifiez votre clé API HeyGen.</span>
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={loading || !script.trim()}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          {loading ? 'Génération...' : 'Générer la vidéo'}
        </button>
      </form>
    </div>
  )
}
