import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { heygenTranslateVideo, heygenTranslateStatus } from '@/lib/video/engines'

/**
 * POST /api/video/translate — traduction/doublage d'une vidéo avec lip-sync (HeyGen).
 *  - { action: 'start', videoUrl, language, title? } → { translateId }
 *  - { action: 'status', id }                        → { status, url? }
 * Nécessite HEYGEN_API_KEY en prod.
 */
export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non authentifié.' }, { status: 401 })

  let body: any = {}
  try { body = await req.json() } catch { return NextResponse.json({ error: 'Corps invalide' }, { status: 400 }) }

  try {
    if (body.action === 'start') {
      if (!body.videoUrl || !body.language) return NextResponse.json({ error: 'videoUrl et language requis' }, { status: 400 })
      const r = await heygenTranslateVideo(String(body.videoUrl), String(body.language), body.title ? String(body.title) : undefined)
      return NextResponse.json({ success: true, ...r })
    }
    if (body.action === 'status') {
      if (!body.id) return NextResponse.json({ error: 'id requis' }, { status: 400 })
      const s = await heygenTranslateStatus(String(body.id))
      return NextResponse.json({ success: true, ...s })
    }
    return NextResponse.json({ error: 'action inconnue (start|status)' }, { status: 400 })
  } catch (e) {
    return NextResponse.json({ success: false, error: String(e instanceof Error ? e.message : e) }, { status: 502 })
  }
}
