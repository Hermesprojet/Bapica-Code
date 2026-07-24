import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { heygenUploadTalkingPhoto, heygenTalkingPhotoVideo } from '@/lib/video/engines'

/**
 * POST /api/video/avatar — crée un avatar à partir d'une PHOTO et le fait parler (HeyGen).
 *  - { action: 'create', imageUrl }                                   → { talkingPhotoId }
 *  - { action: 'generate', talkingPhotoId, script, ratio?, voiceId? } → { taskId } (suivre via /api/video/status, provider HeyGen)
 * Nécessite HEYGEN_API_KEY (+ HEYGEN_VOICE_ID ou voiceId) en prod.
 */
export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non authentifié.' }, { status: 401 })

  let body: any = {}
  try { body = await req.json() } catch { return NextResponse.json({ error: 'Corps invalide' }, { status: 400 }) }

  try {
    if (body.action === 'create') {
      if (!body.imageUrl) return NextResponse.json({ error: 'imageUrl requis' }, { status: 400 })
      const r = await heygenUploadTalkingPhoto(String(body.imageUrl))
      return NextResponse.json({ success: true, ...r })
    }
    if (body.action === 'generate') {
      if (!body.talkingPhotoId || !body.script) return NextResponse.json({ error: 'talkingPhotoId et script requis' }, { status: 400 })
      const r = await heygenTalkingPhotoVideo(
        String(body.talkingPhotoId), String(body.script), String(body.ratio || '9:16'),
        body.voiceId ? String(body.voiceId) : undefined,
      )
      return NextResponse.json({ success: true, ...r })
    }
    return NextResponse.json({ error: 'action inconnue (create|generate)' }, { status: 400 })
  } catch (e) {
    return NextResponse.json({ success: false, error: String(e instanceof Error ? e.message : e) }, { status: 502 })
  }
}
