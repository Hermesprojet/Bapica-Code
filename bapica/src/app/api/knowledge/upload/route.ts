import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { extractText, ingestClientDocument } from '@/lib/client-knowledge'

export const dynamic = 'force-dynamic'
export const maxDuration = 60

/**
 * POST /api/knowledge/upload
 * - multipart/form-data avec un champ `file` (PDF, DOCX, TXT/MD…)
 * - OU JSON { title, text } pour du texte collé
 * Extrait le texte, le découpe, l'embed (OpenAI) et le stocke pour ce client.
 */
export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non authentifié.' }, { status: 401 })

  if (!process.env.OPENAI_API_KEY) {
    return NextResponse.json({ error: 'La base de connaissances est en cours de configuration (clé OpenAI).' }, { status: 503 })
  }

  try {
    let source = ''
    let text = ''
    const ct = req.headers.get('content-type') || ''

    if (ct.includes('multipart/form-data')) {
      const form = await req.formData()
      const file = form.get('file') as File | null
      if (!file) return NextResponse.json({ error: 'Aucun fichier.' }, { status: 400 })
      if (file.size > 8 * 1024 * 1024) return NextResponse.json({ error: 'Fichier trop volumineux (max 8 Mo).' }, { status: 400 })
      const buffer = Buffer.from(await file.arrayBuffer())
      source = file.name
      text = await extractText(file.name, buffer)
    } else {
      const body = await req.json()
      source = (body?.title || 'Note').toString().slice(0, 120)
      text = (body?.text || '').toString()
    }

    if (!text.trim()) {
      return NextResponse.json({ error: 'Aucun texte exploitable dans ce document.' }, { status: 422 })
    }

    const { inserted } = await ingestClientDocument(user.id, source, text)
    if (inserted === 0) {
      return NextResponse.json({ error: 'Document trop court ou vide après extraction.' }, { status: 422 })
    }
    return NextResponse.json({ success: true, source, chunks: inserted })
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : String(e) }, { status: 500 })
  }
}
