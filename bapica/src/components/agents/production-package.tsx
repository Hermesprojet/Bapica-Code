'use client'

import { useState } from 'react'
import {
  Sparkles, Film, Mic, Music, Captions, Target, Hash,
  Copy, Check, Clapperboard, Loader2, Download, AlertCircle,
} from 'lucide-react'
import { supabase } from '@/lib/supabase'
import type { ProductionPackage, ProductionScene } from '@/lib/video/maya'

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

async function authHeaders(): Promise<Record<string, string>> {
  const { data: { session } } = await supabase.auth.getSession()
  return { 'Content-Type': 'application/json', Authorization: `Bearer ${session?.access_token || ''}` }
}

// Interroge /api/video/status jusqu'à obtenir l'URL (ou échec / expiration ~5 min).
async function pollUntilDone(provider: string, taskId: string, onTick?: (n: number) => void): Promise<string> {
  const headers = await authHeaders()
  for (let i = 0; i < 60; i++) {
    await sleep(5000)
    onTick?.(i)
    const res = await fetch('/api/video/status', { method: 'POST', headers, body: JSON.stringify({ provider, taskId }) })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || 'Erreur de statut')
    if (data.status === 'succeeded' && data.url) return data.url
    if (data.status === 'failed') throw new Error('Le moteur a échoué à générer ce plan.')
  }
  throw new Error('Délai dépassé. Réessayez.')
}

const engineColor: Record<string, string> = {
  Runway: 'bg-purple-100 text-purple-700',
  Veo: 'bg-blue-100 text-blue-700',
  HeyGen: 'bg-emerald-100 text-emerald-700',
  Kling: 'bg-pink-100 text-pink-700',
  Luma: 'bg-amber-100 text-amber-700',
  'Best Available': 'bg-slate-100 text-slate-700',
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={async () => {
        try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500) } catch {}
      }}
      className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs font-medium text-muted-foreground hover:bg-muted transition-colors"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-green-600" /> : <Copy className="h-3.5 w-3.5" />}
      {copied ? 'Copié' : 'Copier le prompt'}
    </button>
  )
}

function SceneCard({ scene, ratio }: { scene: ProductionScene; ratio: string }) {
  const [state, setState] = useState<'idle' | 'rendering' | 'done' | 'error'>('idle')
  const [msg, setMsg] = useState('')
  const [url, setUrl] = useState('')

  const generateClip = async () => {
    if (state === 'rendering') return
    setState('rendering'); setMsg('Initialisation…'); setUrl('')
    try {
      const headers = await authHeaders()
      const isAvatar = scene.recommendedEngine === 'HeyGen'
      // Étape 1 : démarrage (keyframe Runway, ou vidéo avatar HeyGen).
      let res = await fetch('/api/video/render', {
        method: 'POST', headers,
        body: JSON.stringify({ action: 'scene', engine: scene.recommendedEngine, visualPrompt: scene.visualPrompt, dialogue: scene.dialogue, ratio, avatar: isAvatar }),
      })
      let data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Erreur de démarrage')
      setMsg(isAvatar ? 'Génération de la vidéo…' : 'Génération du plan…')
      let mediaUrl = await pollUntilDone(data.provider, data.taskId)

      // Étape 2 (Runway) : animer le keyframe en vidéo.
      if (data.provider === 'Runway' && data.kind === 'image') {
        setMsg('Animation du plan…')
        res = await fetch('/api/video/render', {
          method: 'POST', headers,
          body: JSON.stringify({ action: 'animate', imageUrl: mediaUrl, visualPrompt: scene.visualPrompt, ratio }),
        })
        data = await res.json()
        if (!res.ok) throw new Error(data.error || 'Erreur d\'animation')
        mediaUrl = await pollUntilDone(data.provider, data.taskId)
      }
      setUrl(mediaUrl); setState('done')
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e)); setState('error')
    }
  }

  const specs: [string, string][] = [
    ['Décor', scene.decor],
    ['Éclairage', scene.lighting],
    ['Ambiance', scene.mood],
    ['Caméra', scene.cameraAngle],
    ['Mouvement', scene.cameraMovement],
    ['Émotion', scene.emotion],
    ['SFX', scene.sfx],
  ]
  return (
    <div className="card-professional p-5">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-xs font-bold text-primary">{scene.n}</span>
          <h4 className="font-semibold text-sm">{scene.title}</h4>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">{scene.duration}</span>
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${engineColor[scene.recommendedEngine] || engineColor['Best Available']}`}>{scene.recommendedEngine}</span>
        </div>
      </div>

      <div className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2 mb-3">
        {specs.filter(([, v]) => v).map(([k, v]) => (
          <div key={k} className="flex gap-2 text-xs">
            <span className="shrink-0 font-medium text-muted-foreground">{k} :</span>
            <span className="text-foreground/90">{v}</span>
          </div>
        ))}
      </div>

      {scene.dialogue && (
        <p className="mb-3 rounded-lg bg-muted/60 px-3 py-2 text-sm italic text-foreground/90">« {scene.dialogue} »</p>
      )}

      <div className="rounded-lg border border-border bg-muted/40 p-3">
        <div className="mb-1.5 flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Prompt visuel (moteur)</span>
          <CopyButton text={scene.visualPrompt} />
        </div>
        <p className="font-mono text-xs leading-relaxed text-foreground/80">{scene.visualPrompt}</p>
      </div>

      {/* Rendu réel du plan (nécessite les clés moteurs en prod) */}
      <div className="mt-3">
        {state === 'done' && url ? (
          <div className="space-y-2">
            <video src={url} controls className="w-full rounded-lg border border-border bg-black" />
            <a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline">
              <Download className="h-3.5 w-3.5" /> Ouvrir / télécharger le clip
            </a>
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <button
              onClick={generateClip}
              disabled={state === 'rendering'}
              className="inline-flex items-center gap-1.5 rounded-lg border border-primary/30 bg-primary/5 px-3 py-1.5 text-xs font-semibold text-primary hover:bg-primary/10 disabled:opacity-60 transition-colors"
            >
              {state === 'rendering'
                ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> {msg || 'Génération…'}</>
                : <><Clapperboard className="h-3.5 w-3.5" /> Générer le clip ({scene.recommendedEngine})</>}
            </button>
            {state === 'error' && (
              <span className="inline-flex items-center gap-1 text-xs text-destructive"><AlertCircle className="h-3.5 w-3.5 shrink-0" /> {msg}</span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function InfoCard({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="card-professional p-4">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold">{icon} {title}</div>
      <div className="space-y-0.5 text-sm text-foreground/90">{children}</div>
    </div>
  )
}

// Génère la voix off du script via ElevenLabs (renvoie un audio à écouter).
function VoiceButton({ script }: { script: string }) {
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [audioUrl, setAudioUrl] = useState('')
  const [err, setErr] = useState('')

  const generate = async () => {
    if (!script.trim() || state === 'loading') return
    setState('loading'); setErr('')
    try {
      const headers = await authHeaders()
      const res = await fetch('/api/video/render', { method: 'POST', headers, body: JSON.stringify({ action: 'voice', text: script }) })
      if (!res.ok) {
        let m = 'Erreur'
        try { m = (await res.json()).error } catch {}
        throw new Error(m)
      }
      const blob = await res.blob()
      setAudioUrl(URL.createObjectURL(blob)); setState('done')
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e)); setState('error')
    }
  }

  if (state === 'done' && audioUrl) {
    return <audio src={audioUrl} controls className="mt-2 w-full" />
  }
  return (
    <div className="mt-2">
      <button
        onClick={generate}
        disabled={state === 'loading'}
        className="inline-flex items-center gap-1.5 rounded-md border border-primary/30 bg-primary/5 px-2.5 py-1 text-xs font-semibold text-primary hover:bg-primary/10 disabled:opacity-60 transition-colors"
      >
        {state === 'loading' ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Génération…</> : <><Mic className="h-3.5 w-3.5" /> Générer la voix off</>}
      </button>
      {state === 'error' && <p className="mt-1 flex items-center gap-1 text-xs text-destructive"><AlertCircle className="h-3.5 w-3.5 shrink-0" /> {err}</p>}
    </div>
  )
}

export function ProductionPackageView({ pkg }: { pkg: ProductionPackage }) {
  return (
    <div className="space-y-6 animate-slide-up">
      {/* Concept + hook + meta */}
      <div className="card-elevated p-6">
        <div className="flex flex-wrap items-center gap-2 mb-4">
          {[pkg.platform, pkg.ratio, pkg.totalDuration, pkg.objective].filter(Boolean).map((m, i) => (
            <span key={i} className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">{m}</span>
          ))}
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${engineColor[pkg.primaryEngine] || engineColor['Best Available']}`}>Moteur : {pkg.primaryEngine}</span>
        </div>
        <p className="text-sm text-muted-foreground leading-relaxed">{pkg.concept}</p>
        <div className="mt-4 rounded-xl border border-primary/20 bg-primary/5 p-4">
          <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-primary"><Sparkles className="h-3.5 w-3.5" /> Hook (0-3s)</div>
          <p className="text-base font-semibold text-foreground">« {pkg.hook} »</p>
        </div>
      </div>

      {/* Storyboard */}
      <div>
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Film className="h-4 w-4 text-primary" /> Storyboard ({pkg.scenes.length} scènes)</h3>
        <div className="space-y-4">
          {pkg.scenes.map((s) => <SceneCard key={s.n} scene={s} ratio={pkg.ratio} />)}
        </div>
      </div>

      {/* Production : voix / musique / sous-titres */}
      <div className="grid gap-4 md:grid-cols-3">
        <InfoCard icon={<Mic className="h-4 w-4 text-primary" />} title="Voix off">
          <p><span className="text-muted-foreground">Profil :</span> {pkg.voiceover?.profile}</p>
          <p><span className="text-muted-foreground">Ton :</span> {pkg.voiceover?.tone}</p>
          <p className="text-xs text-muted-foreground mt-1">via {pkg.voiceover?.provider}</p>
          <VoiceButton script={pkg.scenes.map((s) => s.dialogue).filter(Boolean).join(' ')} />
        </InfoCard>
        <InfoCard icon={<Music className="h-4 w-4 text-primary" />} title="Musique & SFX">
          <p>{pkg.music}</p>
          {pkg.sfxOverall && <p className="text-xs text-muted-foreground mt-1">{pkg.sfxOverall}</p>}
        </InfoCard>
        <InfoCard icon={<Captions className="h-4 w-4 text-primary" />} title="Sous-titres">
          <p><span className="text-muted-foreground">Style :</span> {pkg.subtitles?.style}</p>
          <p><span className="text-muted-foreground">Animation :</span> {pkg.subtitles?.animation}</p>
        </InfoCard>
      </div>

      {/* Formats + CTA + publication */}
      <div className="card-professional p-6 space-y-4">
        {pkg.formatVariants?.length > 0 && (
          <div>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Adaptations par format</div>
            <div className="flex flex-wrap gap-2">
              {pkg.formatVariants.map((f, i) => <span key={i} className="rounded-lg border border-border px-2.5 py-1 text-xs">{f}</span>)}
            </div>
          </div>
        )}
        <div className="rounded-lg bg-primary/5 border border-primary/20 p-3">
          <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-primary"><Target className="h-3.5 w-3.5" /> CTA final</div>
          <p className="text-sm font-medium">{pkg.cta}</p>
        </div>
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">Titre</div>
          <p className="text-sm font-medium">{pkg.title}</p>
        </div>
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">Description</div>
          <p className="text-sm text-foreground/90 leading-relaxed">{pkg.description}</p>
        </div>
        {pkg.hashtags?.length > 0 && (
          <div className="flex items-start gap-2">
            <Hash className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
            <p className="text-sm text-primary">{pkg.hashtags.map((h) => (h.startsWith('#') ? h : `#${h}`)).join(' ')}</p>
          </div>
        )}
      </div>
    </div>
  )
}
