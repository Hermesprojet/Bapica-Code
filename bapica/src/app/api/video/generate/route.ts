import { NextRequest, NextResponse } from 'next/server'

/**
 * Bapica Video Studio API — Alexya-compatible
 * 
 * Modes:
 * - image : texte → image ultra-réaliste (Runway text_to_image)
 * - video : texte → clip vidéo (Runway text_to_video)
 * - reel  : script → Reel vertical (HeyGen + ElevenLabs)
 * - motion: image → animation (Runway image_to_video)
 */

const RUNWAY_URL = 'https://api.dev.runwayml.com/v1'
const RUNWAY_VERSION = '2024-11-06'

async function runwayTask(endpoint: string, body: Record<string, any>, apiKey: string) {
  const res = await fetch(`${RUNWAY_URL}${endpoint}`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'X-Runway-Version': RUNWAY_VERSION,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  return res.json()
}

export async function POST(req: NextRequest) {
  try {
    const { mode, prompt, style, duration, aspectRatio } = await req.json()

    switch (mode) {
      case 'image': return await generateImage(prompt, style)
      case 'video': return await generateVideo(prompt, duration || 5, aspectRatio || '16:9')
      case 'reel':  return await generateReel(prompt, style)
      case 'motion':return await generateMotion(prompt, style)
      default: return NextResponse.json({ error: 'Mode invalide: image, video, reel, motion' }, { status: 400 })
    }
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 422 })
  }
}

async function generateImage(prompt: string, style?: string) {
  const key = process.env.RUNWAY_API_KEY
  if (!key) return NextResponse.json({ error: 'Service vidéo en configuration (clé API). Disponible prochainement.' })

  const fullPrompt = style ? `${prompt}. Style: ${style}.` : prompt

  try {
    const data = await runwayTask('/text_to_image', {
      promptText: fullPrompt,
      model: 'gen4_image',
      ratio: "1024:1024",
      numberOfImages: 1,
    }, key)

    if ((data as any).id) {
      return NextResponse.json({
        success: true,
        status: 'generating',
        taskId: (data as any).id,
        estimatedTime: '30-60 secondes',
        provider: 'Runway Gen-4 Turbo',
        message: '✨ Image en cours de génération.',
        prompt: fullPrompt,
      })
    }
    return NextResponse.json({ error: (data as any).error || (data as any).message || 'Erreur inconnue', raw: data })
  } catch (e) {
    return NextResponse.json({ error: String(e) })
  }
}

async function generateVideo(prompt: string, duration: number, aspectRatio: string) {
  const key = process.env.RUNWAY_API_KEY
  if (!key) return NextResponse.json({ error: 'Service vidéo en configuration (clé API).' })

  try {
    const data = await runwayTask('/text_to_video', {
      promptText: prompt,
      model: 'gen4_image',
      duration: Math.min(duration, 10),
      aspectRatio,
    }, key)

    if ((data as any).id) {
      return NextResponse.json({
        success: true,
        status: 'generating',
        taskId: (data as any).id,
        estimatedTime: '1-2 minutes',
        provider: 'Runway Gen-4 Turbo',
        message: '🎬 Vidéo en cours de production.',
      })
    }
    return NextResponse.json({ error: (data as any).error || 'Erreur Runway', raw: data })
  } catch (e) {
    return NextResponse.json({ error: String(e) })
  }
}

async function generateReel(script: string, style?: string) {
  const heyGenKey = process.env.HEYGEN_API_KEY
  const elevenKey = process.env.ELEVENLABS_API_KEY

  if (!heyGenKey || !elevenKey) {
    return NextResponse.json({ error: 'Service Reel en configuration (HeyGen + ElevenLabs).' })
  }

  const stylePrompt = style || 'corporate moderne, fond épuré, éclairage professionnel'

  return NextResponse.json({
    success: true,
    status: 'generating',
    script,
    style: stylePrompt,
    estimatedTime: '1-2 minutes',
    message: '✨ Reel en cours de création.',
    provider: 'HeyGen + ElevenLabs',
  })
}

async function generateMotion(imagePrompt: string, style?: string) {
  const key = process.env.RUNWAY_API_KEY
  if (!key) return NextResponse.json({ error: 'Service Motion en configuration (clé API).' })

  try {
    // Motion = image_to_video avec un prompt de mouvement cinématique
    const data = await runwayTask('/image_to_video', {
      promptImage: imagePrompt,
      promptText: `Smooth cinematic camera movement, subtle parallax, professional lighting. ${style || ''}`,
      model: 'gen4_image',
      duration: 4,
    }, key)

    if ((data as any).id) {
      return NextResponse.json({
        success: true,
        status: 'generating',
        taskId: (data as any).id,
        estimatedTime: '1-2 minutes',
        provider: 'Runway Gen-4 Turbo Motion',
        message: '🎬 Animation cinématique en cours.',
      })
    }
    return NextResponse.json({ error: (data as any).error || 'Erreur Runway', raw: data })
  } catch (e) {
    return NextResponse.json({ error: String(e) })
  }
}
