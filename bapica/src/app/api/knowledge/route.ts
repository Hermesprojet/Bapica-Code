import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { listClientDocuments, deleteClientDocument } from '@/lib/client-knowledge'

// GET : liste les documents (regroupés par source) du client.
export async function GET(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non authentifié.' }, { status: 401 })
  try {
    const documents = await listClientDocuments(user.id)
    return NextResponse.json({ success: true, documents })
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : String(e) }, { status: 500 })
  }
}

// DELETE : supprime un document (toutes ses parties).  { source }
export async function DELETE(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non authentifié.' }, { status: 401 })
  let body: any
  try { body = await req.json() } catch { body = {} }
  const source = (body?.source || '').toString()
  if (!source) return NextResponse.json({ error: 'source requis' }, { status: 400 })
  try {
    await deleteClientDocument(user.id, source)
    return NextResponse.json({ success: true })
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : String(e) }, { status: 500 })
  }
}
