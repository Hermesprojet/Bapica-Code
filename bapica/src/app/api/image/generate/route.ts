import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { generateImage, type ImageSize } from '@/lib/image/openai'

/**
 * POST /api/image/generate — génère une image (texte → image) via OpenAI gpt-image-1.
 * Corps : { prompt, size? }. Renvoie { image } (data URL PNG, prêt à afficher/télécharger).
 * Nécessite OPENAI_API_KEY.
 */
const SIZES = new Set<ImageSize>(['1024x1024', '1024x1536', '1536x1024', 'auto'])

export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  let body: any = {}
  try { body = await req.json() } catch { return NextResponse.json({ error: 'Requête invalide.' }, { status: 400 }) }

  const prompt = typeof body.prompt === 'string' ? body.prompt.trim() : ''
  if (!prompt) return NextResponse.json({ error: 'Décrivez l’image à générer.' }, { status: 400 })
  const size: ImageSize = SIZES.has(body.size) ? body.size : '1024x1024'

  try {
    const b64 = await generateImage(prompt, size)
    return NextResponse.json({ image: `data:image/png;base64,${b64}` })
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e)
    if (msg.includes('IMAGE_NOT_CONFIGURED')) {
      return NextResponse.json({ error: 'Génération d’images en cours de configuration (OPENAI_API_KEY manquante).' }, { status: 503 })
    }
    return NextResponse.json({ error: msg }, { status: 502 })
  }
}
