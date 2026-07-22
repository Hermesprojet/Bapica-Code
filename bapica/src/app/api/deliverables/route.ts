import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { listDeliverables, deleteDeliverable } from '@/lib/deliverables/store'

/**
 * GET  /api/deliverables            → liste les documents du client (sans le contenu).
 * DELETE /api/deliverables { id }   → supprime un document.
 * Le téléchargement se fait via GET /api/deliverables/[id].
 */
export async function GET(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  try {
    const documents = await listDeliverables(user.id)
    return NextResponse.json({ documents, needsSetup: false })
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e)
    if (msg.includes('DELIVERABLES_TABLE_MISSING')) {
      return NextResponse.json({ documents: [], needsSetup: true })
    }
    return NextResponse.json({ documents: [], needsSetup: false })
  }
}

export async function DELETE(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  let body: any = {}
  try { body = await req.json() } catch { /* ignore */ }
  const id = typeof body.id === 'string' ? body.id : ''
  if (!id) return NextResponse.json({ error: 'id requis.' }, { status: 400 })
  await deleteDeliverable(user.id, id)
  return NextResponse.json({ success: true })
}
