import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { getDeliverable } from '@/lib/deliverables/store'
import { createSheet, createDoc, parseCsv } from '@/lib/google/workspace'

/**
 * POST /api/deliverables/[id]/google → exporte le document vers Google :
 *   - kind excel/csv → Google Sheet (à partir du CSV stocké)
 *   - sinon          → Google Doc (texte)
 * Nécessite une connexion Google Docs/Sheets (page Connexions). Renvoie l'URL du fichier.
 */
export async function POST(req: NextRequest, { params }: { params: { id: string } }) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const doc = await getDeliverable(user.id, params.id)
  if (!doc) return NextResponse.json({ error: 'Document introuvable.' }, { status: 404 })

  const isTable = doc.kind === 'excel' || doc.kind === 'csv'
  const res = isTable
    ? await createSheet(user.id, doc.title, parseCsv(doc.content))
    : await createDoc(user.id, doc.title, doc.content)

  if (res.ok) return NextResponse.json({ success: true, url: res.url, target: isTable ? 'sheet' : 'doc' })

  const notConnected = res.error === 'not-connected' || res.error === 'no-token'
  return NextResponse.json(
    { error: notConnected ? 'Google Docs/Sheets non connecté (page Connexions).' : res.error },
    { status: notConnected ? 400 : 502 }
  )
}
