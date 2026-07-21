import { NextRequest, NextResponse } from 'next/server'
import { getUserFromToken } from '@/lib/api-auth'
import { googleAuthUrl, googleConfigured } from '@/lib/calendar/providers'

export const dynamic = 'force-dynamic'

/**
 * GET /api/calendar/google/connect?t=<supabase_access_token>
 * Navigation plein écran (pas un fetch) : le jeton Supabase passe en query (HTTPS).
 * On le valide, puis on redirige vers Google en encodant l'uid dans `state`.
 */
export async function GET(req: NextRequest) {
  const back = (q: string) => NextResponse.redirect(new URL(`/dashboard/connections?${q}`, req.nextUrl.origin))

  if (!googleConfigured()) return back('error=' + encodeURIComponent('Google Agenda non configuré (clés API manquantes).'))

  const token = req.nextUrl.searchParams.get('t') || ''
  const user = await getUserFromToken(token)
  if (!user) return back('error=' + encodeURIComponent('Session expirée, reconnectez-vous.'))

  const state = Buffer.from(JSON.stringify({ uid: user.id, n: Math.random().toString(36).slice(2) })).toString('base64url')
  return NextResponse.redirect(googleAuthUrl(state))
}
