import { NextRequest, NextResponse } from 'next/server'
import { exchangeWorkspaceCode, WORKSPACE_PLATFORM } from '@/lib/google/workspace'
import { saveConnection } from '@/lib/social/store'

export const dynamic = 'force-dynamic'

/**
 * GET /api/google/workspace/callback?code=...&state=...
 * Échange le code (access + refresh token) et enregistre la connexion Drive/Docs/Sheets.
 */
export async function GET(req: NextRequest) {
  const back = (q: string) => NextResponse.redirect(new URL(`/dashboard/connections?${q}`, req.nextUrl.origin))

  const err = req.nextUrl.searchParams.get('error_description') || req.nextUrl.searchParams.get('error')
  if (err) return back('error=' + encodeURIComponent(`Google : ${err}`))

  const code = req.nextUrl.searchParams.get('code') || ''
  const state = req.nextUrl.searchParams.get('state') || ''
  if (!code || !state) return back('error=' + encodeURIComponent('Réponse Google incomplète.'))

  let uid = ''
  try { uid = JSON.parse(Buffer.from(state, 'base64url').toString()).uid } catch { /* ignore */ }
  if (!uid) return back('error=' + encodeURIComponent('État invalide, réessayez.'))

  try {
    const { accessToken, refreshToken, expiresIn } = await exchangeWorkspaceCode(code)
    const expiresAt = expiresIn ? new Date(Date.now() + expiresIn * 1000).toISOString() : null
    await saveConnection(uid, WORKSPACE_PLATFORM, { accessToken, refreshToken, expiresAt })
    return back('connected=google_workspace')
  } catch (e) {
    return back('error=' + encodeURIComponent(e instanceof Error ? e.message : String(e)))
  }
}
