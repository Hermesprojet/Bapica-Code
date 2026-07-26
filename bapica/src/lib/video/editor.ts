// Édition / montage vidéo dans le cloud via Shotstack (timeline JSON → MP4).
// Contrairement au montage FFmpeg (route /assemble, indisponible sur Vercel serverless),
// Shotstack tourne côté API : assemblage de clips, musique de fond, sous-titres, format.
//
// ÉCRIT « à l'aveugle » (non testable en sandbox). Prérequis prod : SHOTSTACK_API_KEY
// (compte Shotstack). SHOTSTACK_ENV = 'v1' (prod) par défaut, 'stage' pour l'environnement de test.

import type { RenderStatus } from './engines'

function base(): string {
  const env = process.env.SHOTSTACK_ENV || 'v1'
  return `https://api.shotstack.io/${env}`
}

function aspectRatio(ratio: string): '9:16' | '16:9' | '1:1' {
  const r = (ratio || '').trim()
  if (r === '9:16') return '9:16'
  if (r === '1:1') return '1:1'
  return '16:9'
}

export interface EditSpec {
  clips: { src: string; length?: number; trim?: number }[]  // clips à enchaîner (URLs). trim = secondes à couper AU DÉBUT de la source (point d'entrée)
  soundtrack?: string                          // musique de fond (URL)
  voiceover?: string                           // voix off (URL) — mixée par-dessus
  captions?: string[]                          // sous-titre saisi, par clip (optionnel)
  autoCaptions?: boolean                        // sous-titres AUTOMATIQUES (transcription de l'audio par Shotstack)
  ratio?: string                               // 9:16 | 16:9 | 1:1
}

/** Démarre un rendu de montage. Renvoie l'identifiant à suivre via editStatus. */
export async function startEdit(spec: EditSpec): Promise<{ renderId: string }> {
  const key = process.env.SHOTSTACK_API_KEY
  if (!key) throw new Error('SHOTSTACK_API_KEY manquante')
  const clips = (spec.clips || []).filter((c) => c && c.src)
  if (clips.length === 0) throw new Error('Aucun clip à monter')

  // Piste vidéo : clips enchaînés (durée par défaut 5 s si non fournie).
  // trim = point d'entrée (secondes coupées au début de la source) → permet de DÉCOUPER un segment.
  let cursor = 0
  const videoClips = clips.map((c) => {
    const length = Math.max(1, Number(c.length) || 5)
    const trim = Number(c.trim) > 0 ? Number(c.trim) : undefined
    const asset: Record<string, unknown> = { type: 'video', src: c.src }
    if (trim) asset.trim = trim
    const clip = { asset, start: cursor, length, fit: 'cover' as const }
    cursor += length
    return clip
  })
  const total = cursor

  // Piste sous-titres alignée sur chaque clip.
  const captionClips: any[] = []
  if (Array.isArray(spec.captions)) {
    let start = 0
    clips.forEach((c, i) => {
      const length = Math.max(1, Number(c.length) || 5)
      const text = spec.captions?.[i]
      if (text) {
        captionClips.push({
          asset: { type: 'title', text, style: 'subtitle', size: 'medium', position: 'bottom' },
          start, length,
        })
      }
      start += length
    })
  }

  const tracks: any[] = []
  // Sous-titres AUTOMATIQUES : Shotstack transcrit l'audio et incruste les sous-titres.
  // Piste placée au-dessus de la vidéo. (Écrit à l'aveugle — schéma « caption » Shotstack.)
  if (spec.autoCaptions && clips[0]?.src) {
    tracks.push({
      clips: [{
        asset: { type: 'caption', src: clips[0].src, background: { color: '#000000', opacity: 0.5, padding: 12 } },
        start: 0, length: total,
      }],
    })
  }
  if (captionClips.length) tracks.push({ clips: captionClips })
  tracks.push({ clips: videoClips })
  if (spec.voiceover) tracks.push({ clips: [{ asset: { type: 'audio', src: spec.voiceover, volume: 1 }, start: 0, length: total }] })

  const timeline: any = { background: '#000000', tracks }
  if (spec.soundtrack) timeline.soundtrack = { src: spec.soundtrack, effect: 'fadeInFadeOut', volume: 0.15 }

  const res = await fetch(`${base()}/render`, {
    method: 'POST',
    headers: { 'x-api-key': key, 'Content-Type': 'application/json' },
    body: JSON.stringify({ timeline, output: { format: 'mp4', aspectRatio: aspectRatio(spec.ratio || '9:16'), fps: 30 } }),
    signal: AbortSignal.timeout(15000),
  })
  const data = await res.json()
  const id = data?.response?.id
  if (!res.ok || !id) throw new Error(`Shotstack : ${data?.message || JSON.stringify(data)}`)
  return { renderId: id }
}

export async function editStatus(renderId: string): Promise<RenderStatus> {
  const key = process.env.SHOTSTACK_API_KEY
  if (!key) throw new Error('SHOTSTACK_API_KEY manquante')
  const res = await fetch(`${base()}/render/${encodeURIComponent(renderId)}`, { headers: { 'x-api-key': key } })
  const data = await res.json()
  const s = String(data?.response?.status || '').toLowerCase()
  if (s === 'done') return { status: 'succeeded', url: data.response.url, raw: data }
  if (s === 'failed') return { status: 'failed', raw: data }
  return { status: 'processing', raw: data }
}
