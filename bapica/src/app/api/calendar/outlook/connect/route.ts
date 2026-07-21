import { NextRequest, NextResponse } from 'next/server'
import { getUserFromToken } from '@/lib/api-auth'
import { outlookAuthUrl, outlookConfigured } from '@/lib/calendar/providers'

export const dynamic = 'force-dynamic'

/**
 * GET /api/calendar/outlook/connect?t=<supabase_access_token>
 * Navigation plein écran : le jeton Supabase passe en query (HTTPS). On le valide,
 * puis on redirige vers Microsoft en encodant l'uid dans `state`.
 */
export async function GET(req: NextRequest) {
  const back = (q: string) => NextResponse.redirect(new URL(`/dashboard/connections?${q}`, req.nextUrl.origin))

  if (!outlookConfigured()) return back('error=' + encodeURIComponent('Outlook non configuré (clés API manquantes).'))

  const token = req.nextUrl.searchParams.get('t') || ''
  const user = await getUserFromToken(token)
  if (!user) return back('error=' + encodeURIComponent('Session expirée, reconnectez-vous.'))

  const state = Buffer.from(JSON.stringify({ uid: user.id, n: Math.random().toString(36).slice(2) })).toString('base64url')
  return NextResponse.redirect(outlookAuthUrl(state))
}
