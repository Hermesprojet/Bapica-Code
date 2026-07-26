'use client'

// Panneau « Éditer une vidéo existante » du Studio Vidéo (Maya).
// Donne une URL de vidéo (ex : un clip généré par Maya, ou une vidéo hébergée) puis :
//  - Découper un segment (point d'entrée + durée)  → /api/video/edit (Shotstack)
//  - Sous-titrer automatiquement (transcription)     → /api/video/edit (autoCaptions)
//  - Traduire / doubler avec lip-sync                → /api/video/translate (HeyGen)
// Chaque opération démarre un rendu puis suit son statut jusqu'au lien final.

import { useState } from 'react'
import { supabase } from '@/lib/supabase'
import { Scissors, Captions, Languages, Loader2, Download, ExternalLink } from 'lucide-react'

const LANGUAGES = ['Anglais', 'Espagnol', 'Allemand', 'Italien', 'Portugais', 'Néerlandais', 'Arabe', 'Français']
// HeyGen attend le nom de langue en anglais.
const LANG_MAP: Record<string, string> = {
  Anglais: 'English', Espagnol: 'Spanish', Allemand: 'German', Italien: 'Italian',
  Portugais: 'Portuguese', Néerlandais: 'Dutch', Arabe: 'Arabic', Français: 'French',
}
const RATIOS = ['9:16', '16:9', '1:1']

type JobState = { status: 'idle' | 'running' | 'done' | 'error'; label: string; url?: string; error?: string }

export function VideoEditPanel() {
  const [url, setUrl] = useState('')
  const [ratio, setRatio] = useState('9:16')
  const [trimStart, setTrimStart] = useState('0')
  const [trimLength, setTrimLength] = useState('15')
  const [language, setLanguage] = useState('Anglais')
  const [job, setJob] = useState<JobState>({ status: 'idle', label: '' })

  const token = async () => (await supabase.auth.getSession()).data.session?.access_token || ''

  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

  // Démarre une opération (start) puis suit le statut jusqu'au résultat.
  const runJob = async (endpoint: string, startBody: Record<string, unknown>, label: string) => {
    if (!url.trim() || job.status === 'running') return
    setJob({ status: 'running', label })
    try {
      const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` }
      const startRes = await fetch(endpoint, { method: 'POST', headers, body: JSON.stringify({ action: 'start', ...startBody }) })
      const startData = await startRes.json()
      if (!startRes.ok || startData.success === false || startData.error) {
        setJob({ status: 'error', label, error: startData.error || 'Impossible de démarrer le rendu.' }); return
      }
      const id = startData.renderId || startData.translateId
      if (!id) { setJob({ status: 'error', label, error: 'Aucun identifiant de rendu renvoyé.' }); return }

      // Suivi du statut (jusqu'à ~5 min).
      for (let i = 0; i < 60; i++) {
        await sleep(5000)
        const stRes = await fetch(endpoint, { method: 'POST', headers, body: JSON.stringify({ action: 'status', id }) })
        const st = await stRes.json()
        if (st.status === 'succeeded' && st.url) { setJob({ status: 'done', label, url: st.url }); return }
        if (st.status === 'failed') { setJob({ status: 'error', label, error: 'Le rendu a échoué. Vérifiez la vidéo source.' }); return }
      }
      setJob({ status: 'error', label, error: 'Délai dépassé — réessayez dans un instant.' })
    } catch {
      setJob({ status: 'error', label, error: 'Erreur de connexion. Réessayez.' })
    }
  }

  const cut = () =>
    runJob('/api/video/edit', {
      clips: [{ src: url.trim(), trim: Number(trimStart) || 0, length: Math.max(1, Number(trimLength) || 15) }],
      ratio,
    }, 'Découpage en cours…')

  const subtitle = () =>
    runJob('/api/video/edit', { clips: [{ src: url.trim() }], autoCaptions: true, ratio }, 'Sous-titrage automatique…')

  const translate = () =>
    runJob('/api/video/translate', { videoUrl: url.trim(), language: LANG_MAP[language] || language }, `Traduction en ${language.toLowerCase()}…`)

  const busy = job.status === 'running'

  return (
    <div className="card-elevated p-6">
      <div className="mb-4 flex items-center gap-2">
        <Scissors className="h-5 w-5 text-primary" />
        <h2 className="font-semibold">Éditer une vidéo existante</h2>
      </div>
      <p className="mb-4 text-sm text-muted-foreground">
        Collez l&apos;URL d&apos;une vidéo (un clip généré ici, ou une vidéo hébergée) puis choisissez une opération :
        découper un passage, ajouter des sous-titres automatiques, ou la traduire avec synchronisation labiale.
      </p>

      <label className="mb-1.5 block text-sm font-medium">URL de la vidéo</label>
      <input
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://…/ma-video.mp4"
        className="mb-5 w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
      />

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Découper */}
        <div className="rounded-xl border border-border p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium"><Scissors className="h-4 w-4 text-primary" /> Découper</div>
          <div className="mb-3 flex gap-2">
            <label className="flex-1 text-xs text-muted-foreground">Début (s)
              <input type="number" min={0} value={trimStart} onChange={(e) => setTrimStart(e.target.value)}
                className="mt-1 w-full rounded-lg border border-border bg-background px-2 py-1.5 text-sm focus:border-primary focus:outline-none" />
            </label>
            <label className="flex-1 text-xs text-muted-foreground">Durée (s)
              <input type="number" min={1} value={trimLength} onChange={(e) => setTrimLength(e.target.value)}
                className="mt-1 w-full rounded-lg border border-border bg-background px-2 py-1.5 text-sm focus:border-primary focus:outline-none" />
            </label>
          </div>
          <button onClick={cut} disabled={!url.trim() || busy}
            className="w-full rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors">
            Découper le segment
          </button>
        </div>

        {/* Sous-titrer */}
        <div className="rounded-xl border border-border p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium"><Captions className="h-4 w-4 text-primary" /> Sous-titres auto</div>
          <p className="mb-3 text-xs text-muted-foreground">Transcrit l&apos;audio et incruste les sous-titres dans la vidéo.</p>
          <button onClick={subtitle} disabled={!url.trim() || busy}
            className="w-full rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors">
            Sous-titrer
          </button>
        </div>

        {/* Traduire */}
        <div className="rounded-xl border border-border p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium"><Languages className="h-4 w-4 text-primary" /> Traduire / doubler</div>
          <select value={language} onChange={(e) => setLanguage(e.target.value)}
            className="mb-3 w-full rounded-lg border border-border bg-background px-2 py-1.5 text-sm focus:border-primary focus:outline-none">
            {LANGUAGES.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
          <button onClick={translate} disabled={!url.trim() || busy}
            className="w-full rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors">
            Traduire (lip-sync)
          </button>
        </div>
      </div>

      {/* Format (pour découpe/sous-titres) */}
      <div className="mt-4 flex items-center gap-2 text-sm">
        <span className="text-muted-foreground">Format :</span>
        {RATIOS.map((r) => (
          <button key={r} onClick={() => setRatio(r)}
            className={`rounded-lg border px-3 py-1 text-xs transition-colors ${ratio === r ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-muted'}`}>
            {r}
          </button>
        ))}
      </div>

      {/* Statut / résultat */}
      {job.status !== 'idle' && (
        <div className="mt-5 rounded-xl border border-border bg-muted/40 p-4 text-sm">
          {job.status === 'running' && <div className="flex items-center gap-2 text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> {job.label} (cela peut prendre 1 à 3 minutes)</div>}
          {job.status === 'error' && <div className="text-destructive">{job.error}</div>}
          {job.status === 'done' && job.url && (
            <div className="flex flex-wrap items-center gap-3">
              <span className="font-medium text-foreground">Vidéo prête :</span>
              <a href={job.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-primary hover:underline"><ExternalLink className="h-4 w-4" /> Ouvrir</a>
              <a href={job.url} download className="inline-flex items-center gap-1.5 text-primary hover:underline"><Download className="h-4 w-4" /> Télécharger</a>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
