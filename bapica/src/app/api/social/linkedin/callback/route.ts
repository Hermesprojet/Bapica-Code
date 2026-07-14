import { NextRequest, NextResponse } from 'next/server'
import { exchangeCode, getMemberSub } from '@/lib/social/linkedin'
import { saveConnection } from '@/lib/social/store'

export const dynamic = 'force-dynamic'

/**
 * GET /api/social/linkedin/callback?code=...&state=...
 * LinkedIn renvoie ici après autorisation. On échange le code, récupère l'id
 * membre, et on enregistre la connexion pour l'utilisateur encodé dans `state`.
 */
export async function GET(req: NextRequest) {
  const back = (q: string) => NextResponse.redirect(new URL(`/dashboard/connections?${q}`, req.nextUrl.origin))

  const err = req.nextUrl.searchParams.get('error_description') || req.nextUrl.searchParams.get('error')
  if (err) return back('error=' + encodeURIComponent(`LinkedIn : ${err}`))

  const code = req.nextUrl.searchParams.get('code') || ''
  const state = req.nextUrl.searchParams.get('state') || ''
  if (!code || !state) return back('error=' + encodeURIComponent('Réponse LinkedIn incomplète.'))

  let uid = ''
  try { uid = JSON.parse(Buffer.from(state, 'base64url').toString()).uid } catch { /* ignore */ }
  if (!uid) return back('error=' + encodeURIComponent('État invalide, réessayez.'))

  try {
    const { accessToken, expiresIn } = await exchangeCode(code)
    const sub = await getMemberSub(accessToken)
    const expiresAt = expiresIn ? new Date(Date.now() + expiresIn * 1000).toISOString() : null
    await saveConnection(uid, 'linkedin', { accessToken, expiresAt, externalId: sub })
    return back('connected=linkedin')
  } catch (e) {
    return back('error=' + encodeURIComponent(e instanceof Error ? e.message : String(e)))
  }
}
