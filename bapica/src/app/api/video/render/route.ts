import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { startSceneRender, runwayImageToVideo, elevenlabsTTS } from '@/lib/video/engines'

/**
 * POST /api/video/render
 * Démarre un rendu réel via les moteurs (Runway / HeyGen / ElevenLabs).
 * action:
 *  - "scene"   { engine, visualPrompt, dialogue?, ratio, avatar? } → keyframe (Runway) ou vidéo avatar (HeyGen)
 *  - "animate" { imageUrl, visualPrompt, ratio, duration }        → Runway image→vidéo (étape 2)
 *  - "voice"   { text }                                           → ElevenLabs (renvoie un flux audio/mpeg)
 * Nécessite les clés moteurs en prod ; sinon renvoie une erreur claire.
 */

async function verifyAuth(req: NextRequest): Promise<{ ok: true } | { ok: false; status: 401 | 500; error: string }> {
  const token = (req.headers.get('authorization') || '').replace(/^Bearer\s+/i, '').trim()
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
  const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''
  if (!url || !anon) return { ok: false, status: 500, error: 'Configuration Supabase manquante' }
  if (!token) return { ok: false, status: 401, error: 'Non authentifié.' }
  const supabase = createClient(url, anon, { auth: { persistSession: false, autoRefreshToken: false } })
  const { data: { user }, error } = await supabase.auth.getUser(token)
  if (error || !user) return { ok: false, status: 401, error: 'Non authentifié.' }
  return { ok: true }
}

export async function POST(req: NextRequest) {
  const auth = await verifyAuth(req)
  if (!auth.ok) return NextResponse.json({ error: auth.error }, { status: auth.status })

  let body: any
  try { body = await req.json() } catch { return NextResponse.json({ error: 'Corps invalide' }, { status: 400 }) }
  const action = body?.action

  try {
    if (action === 'scene') {
      const start = await startSceneRender({
        engine: body.engine || 'Runway',
        visualPrompt: (body.visualPrompt || '').toString(),
        dialogue: (body.dialogue || '').toString(),
        ratio: (body.ratio || '9:16').toString(),
        avatar: !!body.avatar,
      })
      return NextResponse.json({ success: true, ...start })
    }

    if (action === 'animate') {
      if (!body.imageUrl) return NextResponse.json({ error: 'imageUrl requis' }, { status: 400 })
      const start = await runwayImageToVideo(
        body.imageUrl.toString(),
        (body.visualPrompt || '').toString(),
        (body.ratio || '9:16').toString(),
        Number(body.duration) || 5,
      )
      return NextResponse.json({ success: true, ...start })
    }

    if (action === 'voice') {
      const text = (body.text || '').toString().trim()
      if (!text) return NextResponse.json({ error: 'Texte requis' }, { status: 400 })
      const audio = await elevenlabsTTS(text)
      return new NextResponse(audio, {
        status: 200,
        headers: { 'Content-Type': 'audio/mpeg', 'Cache-Control': 'no-store' },
      })
    }

    return NextResponse.json({ error: 'action invalide (scene | animate | voice)' }, { status: 400 })
  } catch (e) {
    // On remonte le message brut du moteur pour faciliter le débogage en prod.
    return NextResponse.json({ error: String(e instanceof Error ? e.message : e) }, { status: 502 })
  }
}
