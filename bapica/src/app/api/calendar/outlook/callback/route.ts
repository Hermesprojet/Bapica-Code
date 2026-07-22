import { NextRequest, NextResponse } from 'next/server'
import { exchangeOutlookCode } from '@/lib/calendar/providers'
import { saveConnection } from '@/lib/social/store'

export const dynamic = 'force-dynamic'

/**
 * GET /api/calendar/outlook/callback?code=...&state=...
 * Microsoft renvoie ici après autorisation. On échange le code (access + refresh token)
 * et on enregistre la connexion pour l'utilisateur encodé dans `state`.
 */
export async function GET(req: NextRequest) {
  const back = (q: string) => NextResponse.redirect(new URL(`/dashboard/connections?${q}`, req.nextUrl.origin))

  const err = req.nextUrl.searchParams.get('error_description') || req.nextUrl.searchParams.get('error')
  if (err) return back('error=' + encodeURIComponent(`Microsoft : ${err}`))

  const code = req.nextUrl.searchParams.get('code') || ''
  const state = req.nextUrl.searchParams.get('state') || ''
  if (!code || !state) return back('error=' + encodeURIComponent('Réponse Microsoft incomplète.'))

  let uid = ''
  try { uid = JSON.parse(Buffer.from(state, 'base64url').toString()).uid } catch { /* ignore */ }
  if (!uid) return back('error=' + encodeURIComponent('État invalide, réessayez.'))

  try {
    const { accessToken, refreshToken, expiresIn } = await exchangeOutlookCode(code)
    const expiresAt = expiresIn ? new Date(Date.now() + expiresIn * 1000).toISOString() : null
    await saveConnection(uid, 'outlook_calendar', { accessToken, refreshToken, expiresAt })
    return back('connected=outlook_calendar')
  } catch (e) {
    return back('error=' + encodeURIComponent(e instanceof Error ? e.message : String(e)))
  }
}
