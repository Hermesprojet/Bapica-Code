import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { editImage, type ImageSize } from '@/lib/image/openai'

/**
 * POST /api/image/edit — modifie une image existante selon une consigne (OpenAI gpt-image-1).
 * Multipart : image (fichier) + prompt (consigne) + size?. Renvoie { image } (data URL PNG).
 * L'image reste sous la limite ~4,5 Mo des routes Vercel (contrairement aux vidéos). Nécessite OPENAI_API_KEY.
 */
const SIZES = new Set<ImageSize>(['1024x1024', '1024x1536', '1536x1024', 'auto'])

export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  let form: FormData
  try { form = await req.formData() } catch { return NextResponse.json({ error: 'Requête invalide.' }, { status: 400 }) }

  const file = form.get('image')
  const prompt = String(form.get('prompt') || '').trim()
  const sizeRaw = String(form.get('size') || '1024x1024') as ImageSize
  const size: ImageSize = SIZES.has(sizeRaw) ? sizeRaw : '1024x1024'

  if (!(file instanceof Blob) || file.size === 0) return NextResponse.json({ error: 'Image manquante.' }, { status: 400 })
  if (!file.type.startsWith('image/')) return NextResponse.json({ error: 'Le fichier doit être une image (png, jpg…).' }, { status: 400 })
  if (file.size > 4 * 1024 * 1024) return NextResponse.json({ error: 'Image trop volumineuse (max 4 Mo).' }, { status: 400 })
  if (!prompt) return NextResponse.json({ error: 'Indiquez la modification souhaitée.' }, { status: 400 })

  try {
    const b64 = await editImage(file, prompt, size)
    return NextResponse.json({ image: `data:image/png;base64,${b64}` })
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e)
    if (msg.includes('IMAGE_NOT_CONFIGURED')) {
      return NextResponse.json({ error: 'Retouche d’images en cours de configuration (OPENAI_API_KEY manquante).' }, { status: 503 })
    }
    return NextResponse.json({ error: msg }, { status: 502 })
  }
}
