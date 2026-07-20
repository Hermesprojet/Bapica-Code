import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { logSignal } from '@/lib/insights/store'

/**
 * POST /api/feedback — feedback explicite d'un utilisateur (pouce bas + commentaire).
 * Alimente l'apprentissage produit. Auth optionnelle (visiteur ou client).
 */
export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))

  let b: any = {}
  try { b = await req.json() } catch { return NextResponse.json({ error: 'Requête invalide.' }, { status: 400 }) }

  const content = typeof b.content === 'string' ? b.content.trim() : ''
  const context = typeof b.context === 'string' ? b.context.trim() : ''
  if (!content) return NextResponse.json({ error: 'Contenu requis.' }, { status: 400 })

  await logSignal('feedback', content, { userId: user?.id, meta: { context: context.slice(0, 500) } })
  return NextResponse.json({ success: true })
}
