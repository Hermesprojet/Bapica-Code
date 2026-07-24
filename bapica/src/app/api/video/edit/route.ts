import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { startEdit, editStatus, type EditSpec } from '@/lib/video/editor'

/**
 * POST /api/video/edit — montage/édition cloud (Shotstack) : enchaîne des clips + musique
 * + voix off + sous-titres en une vidéo montée (fonctionne en serverless, contrairement à FFmpeg).
 *  - { action: 'start', clips: [{src,length?}], soundtrack?, voiceover?, captions?, ratio? } → { renderId }
 *  - { action: 'status', id }                                                               → { status, url? }
 * Nécessite SHOTSTACK_API_KEY en prod.
 */
export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non authentifié.' }, { status: 401 })

  let body: any = {}
  try { body = await req.json() } catch { return NextResponse.json({ error: 'Corps invalide' }, { status: 400 }) }

  try {
    if (body.action === 'start') {
      const spec: EditSpec = {
        clips: Array.isArray(body.clips) ? body.clips.map((c: any) => ({ src: String(c?.src || ''), length: c?.length ? Number(c.length) : undefined })) : [],
        soundtrack: body.soundtrack ? String(body.soundtrack) : undefined,
        voiceover: body.voiceover ? String(body.voiceover) : undefined,
        captions: Array.isArray(body.captions) ? body.captions.map(String) : undefined,
        ratio: body.ratio ? String(body.ratio) : '9:16',
      }
      const r = await startEdit(spec)
      return NextResponse.json({ success: true, ...r })
    }
    if (body.action === 'status') {
      if (!body.id) return NextResponse.json({ error: 'id requis' }, { status: 400 })
      const s = await editStatus(String(body.id))
      return NextResponse.json({ success: true, ...s })
    }
    return NextResponse.json({ error: 'action inconnue (start|status)' }, { status: 400 })
  } catch (e) {
    return NextResponse.json({ success: false, error: String(e instanceof Error ? e.message : e) }, { status: 502 })
  }
}
