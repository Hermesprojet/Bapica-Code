import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { getDeliverable } from '@/lib/deliverables/store'
import { isBinaryDeliverableMime } from '@/lib/deliverables'

/**
 * GET /api/deliverables/[id] → renvoie le fichier (téléchargement), scopé à l'utilisateur.
 * Auth Bearer : le tableau de bord récupère le blob avec le jeton puis déclenche le download.
 */
export async function GET(req: NextRequest, { params }: { params: { id: string } }) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const doc = await getDeliverable(user.id, params.id)
  if (!doc) return NextResponse.json({ error: 'Document introuvable.' }, { status: 404 })

  // Nom de fichier ASCII sûr pour l'en-tête + variante UTF-8 (RFC 5987).
  const asciiName = doc.filename.replace(/[^\x20-\x7E]/g, '_').replace(/"/g, '')
  // Les formats Office (.docx/.pptx) sont stockés en base64 → décodés en binaire ici.
  const body: BodyInit = isBinaryDeliverableMime(doc.mime) ? new Blob([new Uint8Array(Buffer.from(doc.content, 'base64'))]) : doc.content
  return new NextResponse(body, {
    status: 200,
    headers: {
      'Content-Type': doc.mime,
      'Content-Disposition': `attachment; filename="${asciiName}"; filename*=UTF-8''${encodeURIComponent(doc.filename)}`,
      'Cache-Control': 'private, no-store',
    },
  })
}
