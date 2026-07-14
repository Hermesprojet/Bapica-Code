'use client'

import { useState } from 'react'
import {
  Sparkles, Film, Mic, Music, Captions, Target, Hash,
} from 'lucide-react'
import { Copy, Check } from 'lucide-react'
import type { ProductionPackage, ProductionScene } from '@/lib/video/maya'

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

function SceneCard({ scene }: { scene: ProductionScene }) {
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
          {pkg.scenes.map((s) => <SceneCard key={s.n} scene={s} />)}
        </div>
      </div>

      {/* Production : voix / musique / sous-titres */}
      <div className="grid gap-4 md:grid-cols-3">
        <InfoCard icon={<Mic className="h-4 w-4 text-primary" />} title="Voix off">
          <p><span className="text-muted-foreground">Profil :</span> {pkg.voiceover?.profile}</p>
          <p><span className="text-muted-foreground">Ton :</span> {pkg.voiceover?.tone}</p>
          <p className="text-xs text-muted-foreground mt-1">via {pkg.voiceover?.provider}</p>
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
