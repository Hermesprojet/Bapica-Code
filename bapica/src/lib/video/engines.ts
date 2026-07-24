// Couche de RENDU — appelle les moteurs de génération (Runway, HeyGen, ElevenLabs).
// ÉCRIT « à l'aveugle » : non testable dans le sandbox (pas de clés + réseau
// bloqué). Les contrats d'API suivent la doc connue ; ils peuvent nécessiter
// un petit ajustement au premier test en production. Toutes les fonctions
// remontent l'erreur brute du moteur pour faciliter le débogage en prod.

export type RenderKind = 'image' | 'video' | 'audio'

export interface RenderStart {
  provider: string
  kind: RenderKind
  taskId: string
}

export interface RenderStatus {
  status: 'processing' | 'succeeded' | 'failed'
  url?: string
  raw?: unknown
}

// Convertit un ratio "9:16" en dimensions Runway/HeyGen.
export function ratioToDim(ratio: string): { width: number; height: number; runway: string } {
  switch ((ratio || '').trim()) {
    case '9:16': return { width: 720, height: 1280, runway: '720:1280' }
    case '1:1': return { width: 1080, height: 1080, runway: '960:960' }
    case '16:9':
    default: return { width: 1280, height: 720, runway: '1280:720' }
  }
}

/* ─────────────────────────  RUNWAY  ───────────────────────── */
const RUNWAY_URL = 'https://api.dev.runwayml.com/v1'
const RUNWAY_VERSION = '2024-11-06'

function runwayHeaders(key: string) {
  return {
    Authorization: `Bearer ${key}`,
    'X-Runway-Version': RUNWAY_VERSION,
    'Content-Type': 'application/json',
  }
}

// Étape 1 : texte → image (keyframe de la scène).
export async function runwayTextToImage(prompt: string, ratio: string): Promise<RenderStart> {
  const key = process.env.RUNWAY_API_KEY
  if (!key) throw new Error('RUNWAY_API_KEY manquante')
  const dim = ratioToDim(ratio)
  const res = await fetch(`${RUNWAY_URL}/text_to_image`, {
    method: 'POST',
    headers: runwayHeaders(key),
    body: JSON.stringify({ promptText: prompt.slice(0, 1000), model: 'gen4_image', ratio: dim.runway }),
  })
  const data = await res.json()
  if (!res.ok || !data?.id) throw new Error(`Runway (image) : ${data?.error || JSON.stringify(data)}`)
  return { provider: 'Runway', kind: 'image', taskId: data.id }
}

// Étape 2 : image → vidéo (anime le keyframe).
export async function runwayImageToVideo(imageUrl: string, prompt: string, ratio: string, duration: number): Promise<RenderStart> {
  const key = process.env.RUNWAY_API_KEY
  if (!key) throw new Error('RUNWAY_API_KEY manquante')
  const dim = ratioToDim(ratio)
  const res = await fetch(`${RUNWAY_URL}/image_to_video`, {
    method: 'POST',
    headers: runwayHeaders(key),
    body: JSON.stringify({
      promptImage: imageUrl,
      promptText: prompt.slice(0, 1000),
      model: 'gen4_turbo',
      ratio: dim.runway,
      duration: duration >= 10 ? 10 : 5,
    }),
  })
  const data = await res.json()
  if (!res.ok || !data?.id) throw new Error(`Runway (vidéo) : ${data?.error || JSON.stringify(data)}`)
  return { provider: 'Runway', kind: 'video', taskId: data.id }
}

export async function runwayStatus(taskId: string): Promise<RenderStatus> {
  const key = process.env.RUNWAY_API_KEY
  if (!key) throw new Error('RUNWAY_API_KEY manquante')
  const res = await fetch(`${RUNWAY_URL}/tasks/${taskId}`, { headers: runwayHeaders(key) })
  const data = await res.json()
  const s = String(data?.status || '').toUpperCase()
  if (s === 'SUCCEEDED') {
    const url = Array.isArray(data.output) ? data.output[0] : data.output
    return { status: 'succeeded', url, raw: data }
  }
  if (s === 'FAILED' || s === 'CANCELLED') return { status: 'failed', raw: data }
  return { status: 'processing', raw: data }
}

/* ─────────────────────────  HEYGEN  ───────────────────────── */
const HEYGEN_URL = 'https://api.heygen.com'

// Avatar parlant : script → vidéo présentateur. HeyGen gère la voix (voice_id).
export async function heygenAvatarVideo(script: string, ratio: string): Promise<RenderStart> {
  const key = process.env.HEYGEN_API_KEY
  if (!key) throw new Error('HEYGEN_API_KEY manquante')
  const avatarId = process.env.HEYGEN_AVATAR_ID
  const voiceId = process.env.HEYGEN_VOICE_ID
  if (!avatarId || !voiceId) {
    throw new Error('HEYGEN_AVATAR_ID et HEYGEN_VOICE_ID requis (choisis un avatar et une voix dans ton compte HeyGen)')
  }
  const dim = ratioToDim(ratio)
  const res = await fetch(`${HEYGEN_URL}/v2/video/generate`, {
    method: 'POST',
    headers: { 'X-Api-Key': key, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      video_inputs: [{
        character: { type: 'avatar', avatar_id: avatarId, avatar_style: 'normal' },
        voice: { type: 'text', input_text: script.slice(0, 1500), voice_id: voiceId },
      }],
      dimension: { width: dim.width, height: dim.height },
    }),
  })
  const data = await res.json()
  const videoId = data?.data?.video_id
  if (!res.ok || !videoId) throw new Error(`HeyGen : ${data?.error?.message || data?.message || JSON.stringify(data)}`)
  return { provider: 'HeyGen', kind: 'video', taskId: videoId }
}

export async function heygenStatus(videoId: string): Promise<RenderStatus> {
  const key = process.env.HEYGEN_API_KEY
  if (!key) throw new Error('HEYGEN_API_KEY manquante')
  const res = await fetch(`${HEYGEN_URL}/v1/video_status.get?video_id=${encodeURIComponent(videoId)}`, {
    headers: { 'X-Api-Key': key },
  })
  const data = await res.json()
  const s = String(data?.data?.status || '')
  if (s === 'completed') return { status: 'succeeded', url: data.data.video_url, raw: data }
  if (s === 'failed') return { status: 'failed', raw: data }
  return { status: 'processing', raw: data }
}

// Avatar à partir d'une PHOTO du client (« talking photo ») : on téléverse l'image chez
// HeyGen puis on génère une vidéo où cette photo parle. Permet de « créer un avatar ».
export async function heygenUploadTalkingPhoto(imageUrl: string): Promise<{ talkingPhotoId: string }> {
  const key = process.env.HEYGEN_API_KEY
  if (!key) throw new Error('HEYGEN_API_KEY manquante')
  const img = await fetch(imageUrl, { signal: AbortSignal.timeout(20000) })
  if (!img.ok) throw new Error(`Image inaccessible : HTTP ${img.status}`)
  const bytes = await img.arrayBuffer()
  const contentType = img.headers.get('content-type') || (/\.png($|\?)/i.test(imageUrl) ? 'image/png' : 'image/jpeg')
  const res = await fetch('https://upload.heygen.com/v1/talking_photo', {
    method: 'POST',
    headers: { 'X-Api-Key': key, 'Content-Type': contentType },
    body: bytes,
  })
  const data = await res.json()
  const id = data?.data?.talking_photo_id
  if (!res.ok || !id) throw new Error(`HeyGen (photo) : ${data?.error?.message || data?.message || JSON.stringify(data)}`)
  return { talkingPhotoId: id }
}

// Génère une vidéo où l'avatar-photo parle le script fourni.
export async function heygenTalkingPhotoVideo(talkingPhotoId: string, script: string, ratio: string, voiceId?: string): Promise<RenderStart> {
  const key = process.env.HEYGEN_API_KEY
  if (!key) throw new Error('HEYGEN_API_KEY manquante')
  const voice = voiceId || process.env.HEYGEN_VOICE_ID
  if (!voice) throw new Error('HEYGEN_VOICE_ID requis (choisis une voix dans ton compte HeyGen)')
  const dim = ratioToDim(ratio)
  const res = await fetch(`${HEYGEN_URL}/v2/video/generate`, {
    method: 'POST',
    headers: { 'X-Api-Key': key, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      video_inputs: [{
        character: { type: 'talking_photo', talking_photo_id: talkingPhotoId },
        voice: { type: 'text', input_text: script.slice(0, 1500), voice_id: voice },
      }],
      dimension: { width: dim.width, height: dim.height },
    }),
  })
  const data = await res.json()
  const videoId = data?.data?.video_id
  if (!res.ok || !videoId) throw new Error(`HeyGen (talking photo) : ${data?.error?.message || data?.message || JSON.stringify(data)}`)
  return { provider: 'HeyGen', kind: 'video', taskId: videoId }
}

/* ─────────────────────────  HEYGEN — TRADUCTION / DOUBLAGE  ───────────────────────── */
// Traduit une vidéo dans une autre langue avec synchronisation labiale (lip-sync).
export async function heygenTranslateVideo(videoUrl: string, outputLanguage: string, title?: string): Promise<{ translateId: string }> {
  const key = process.env.HEYGEN_API_KEY
  if (!key) throw new Error('HEYGEN_API_KEY manquante')
  const res = await fetch(`${HEYGEN_URL}/v2/video_translate`, {
    method: 'POST',
    headers: { 'X-Api-Key': key, 'Content-Type': 'application/json' },
    body: JSON.stringify({ video_url: videoUrl, output_language: outputLanguage, title: title || 'Bapica translation' }),
  })
  const data = await res.json()
  const id = data?.data?.video_translate_id
  if (!res.ok || !id) throw new Error(`HeyGen (traduction) : ${data?.error?.message || data?.message || JSON.stringify(data)}`)
  return { translateId: id }
}

export async function heygenTranslateStatus(translateId: string): Promise<RenderStatus> {
  const key = process.env.HEYGEN_API_KEY
  if (!key) throw new Error('HEYGEN_API_KEY manquante')
  const res = await fetch(`${HEYGEN_URL}/v2/video_translate/${encodeURIComponent(translateId)}`, { headers: { 'X-Api-Key': key } })
  const data = await res.json()
  const s = String(data?.data?.status || '').toLowerCase()
  if (s === 'success') return { status: 'succeeded', url: data.data.url, raw: data }
  if (s === 'failed') return { status: 'failed', raw: data }
  return { status: 'processing', raw: data }
}

/* ─────────────────────────  ELEVENLABS (voix off)  ───────────────────────── */
const ELEVEN_URL = 'https://api.elevenlabs.io/v1'

// Retourne les octets audio (audio/mpeg) — le client les récupère en blob.
export async function elevenlabsTTS(text: string): Promise<ArrayBuffer> {
  const key = process.env.ELEVENLABS_API_KEY
  if (!key) throw new Error('ELEVENLABS_API_KEY manquante')
  const voiceId = process.env.ELEVENLABS_VOICE_ID || '21m00Tcm4TlvDq8ikWAM' // voix par défaut (Rachel)
  const res = await fetch(`${ELEVEN_URL}/text-to-speech/${voiceId}`, {
    method: 'POST',
    headers: { 'xi-api-key': key, 'Content-Type': 'application/json', Accept: 'audio/mpeg' },
    body: JSON.stringify({ text: text.slice(0, 2500), model_id: 'eleven_multilingual_v2' }),
  })
  if (!res.ok) {
    let msg = ''
    try { msg = JSON.stringify(await res.json()) } catch { msg = await res.text() }
    throw new Error(`ElevenLabs : ${msg}`)
  }
  return res.arrayBuffer()
}

/* ─────────────────────────  ROUTEUR  ───────────────────────── */
// Démarre le rendu d'une scène selon le moteur recommandé.
// - avatar / HeyGen  → vidéo présentateur (à partir du dialogue).
// - sinon (Runway…)  → étape 1 : keyframe (texte→image). L'animation
//   (image→vidéo) est déclenchée ensuite par le client avec l'URL de l'image.
export async function startSceneRender(opts: {
  engine: string
  visualPrompt: string
  dialogue?: string
  ratio: string
  avatar?: boolean
}): Promise<RenderStart> {
  const useHeyGen = opts.avatar || opts.engine === 'HeyGen'
  if (useHeyGen) {
    const script = (opts.dialogue || opts.visualPrompt).trim()
    return heygenAvatarVideo(script, opts.ratio)
  }
  // Runway (et moteurs non encore câblés) : on démarre par le keyframe.
  return runwayTextToImage(opts.visualPrompt, opts.ratio)
}

export async function pollStatus(provider: string, taskId: string): Promise<RenderStatus> {
  if (provider === 'HeyGen') return heygenStatus(taskId)
  return runwayStatus(taskId)
}
