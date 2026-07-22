import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { listTags, deleteTag } from '@/lib/tags/store'

/**
 * GET    /api/tags?tag=<valeur>   → liste les étiquettes du client (filtre optionnel).
 * DELETE /api/tags { id }         → supprime une étiquette.
 */
export async function GET(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  const tag = req.nextUrl.searchParams.get('tag') || undefined
  try {
    const tags = await listTags(user.id, tag)
    return NextResponse.json({ tags, needsSetup: false })
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e)
    if (msg.includes('TAGS_TABLE_MISSING')) return NextResponse.json({ tags: [], needsSetup: true })
    return NextResponse.json({ tags: [], needsSetup: false })
  }
}

export async function DELETE(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  let body: any = {}
  try { body = await req.json() } catch { /* ignore */ }
  const id = typeof body.id === 'string' ? body.id : ''
  if (!id) return NextResponse.json({ error: 'id requis.' }, { status: 400 })
  await deleteTag(user.id, id)
  return NextResponse.json({ success: true })
}
