import { NextRequest, NextResponse } from 'next/server'
import { getUserFromToken } from '@/lib/api-auth'
import { workspaceAuthUrl, workspaceConfigured } from '@/lib/google/workspace'

export const dynamic = 'force-dynamic'

/**
 * GET /api/google/workspace/connect?t=<supabase_access_token>
 * Redirige vers Google (scopes Drive/Docs/Sheets), uid encodé dans `state`.
 */
export async function GET(req: NextRequest) {
  const back = (q: string) => NextResponse.redirect(new URL(`/dashboard/connections?${q}`, req.nextUrl.origin))
  if (!workspaceConfigured()) return back('error=' + encodeURIComponent('Google Docs/Sheets non configuré (clés API manquantes).'))

  const token = req.nextUrl.searchParams.get('t') || ''
  const user = await getUserFromToken(token)
  if (!user) return back('error=' + encodeURIComponent('Session expirée, reconnectez-vous.'))

  const state = Buffer.from(JSON.stringify({ uid: user.id, n: Math.random().toString(36).slice(2) })).toString('base64url')
  return NextResponse.redirect(workspaceAuthUrl(state))
}
