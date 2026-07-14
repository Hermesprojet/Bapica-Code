import { NextRequest, NextResponse } from 'next/server'
import { getUserFromToken } from '@/lib/api-auth'
import { buildAuthUrl, linkedinConfigured } from '@/lib/social/linkedin'

export const dynamic = 'force-dynamic'

/**
 * GET /api/social/linkedin/connect?t=<supabase_access_token>
 * Ouvert par une navigation plein écran (pas un fetch), donc le jeton Supabase
 * est passé en query (sur HTTPS). On le valide, puis on redirige vers LinkedIn
 * en encodant l'id utilisateur dans le paramètre `state` (le jeton n'est PAS
 * transmis à LinkedIn).
 */
export async function GET(req: NextRequest) {
  const back = (q: string) => NextResponse.redirect(new URL(`/dashboard/connections?${q}`, req.nextUrl.origin))

  if (!linkedinConfigured()) return back('error=' + encodeURIComponent('LinkedIn non configuré (clés API manquantes).'))

  const token = req.nextUrl.searchParams.get('t') || ''
  const user = await getUserFromToken(token)
  if (!user) return back('error=' + encodeURIComponent('Session expirée, reconnectez-vous.'))

  // state = base64url({ uid, n }) — porte l'id utilisateur à travers LinkedIn.
  const state = Buffer.from(JSON.stringify({ uid: user.id, n: Math.random().toString(36).slice(2) })).toString('base64url')
  return NextResponse.redirect(buildAuthUrl(state))
}
