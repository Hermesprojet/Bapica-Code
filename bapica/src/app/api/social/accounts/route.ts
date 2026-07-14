import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { listPlatforms, deleteConnection } from '@/lib/social/store'

// GET : liste les plateformes connectées de l'utilisateur.
export async function GET(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non authentifié.' }, { status: 401 })
  try {
    const platforms = await listPlatforms(user.id)
    return NextResponse.json({ success: true, platforms })
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : String(e) }, { status: 500 })
  }
}

// DELETE : déconnecte une plateforme.  { platform }
export async function DELETE(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non authentifié.' }, { status: 401 })
  let body: any
  try { body = await req.json() } catch { body = {} }
  const platform = (body?.platform || '').toString()
  if (!platform) return NextResponse.json({ error: 'platform requis' }, { status: 400 })
  try {
    await deleteConnection(user.id, platform)
    return NextResponse.json({ success: true })
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : String(e) }, { status: 500 })
  }
}
