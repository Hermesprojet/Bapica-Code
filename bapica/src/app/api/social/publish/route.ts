import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { getConnection } from '@/lib/social/store'
import { publishText } from '@/lib/social/linkedin'

/**
 * POST /api/social/publish  { text, platforms: ["linkedin"] }
 * Publie le texte sur les plateformes connectées de l'utilisateur.
 * Renvoie un résultat par plateforme (succès + id, ou erreur brute).
 */
export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non authentifié.' }, { status: 401 })

  let body: any
  try { body = await req.json() } catch { return NextResponse.json({ error: 'Corps invalide' }, { status: 400 }) }
  const text = (body?.text || '').toString().trim()
  const platforms: string[] = Array.isArray(body?.platforms) ? body.platforms : []
  if (!text) return NextResponse.json({ error: 'Texte requis' }, { status: 400 })
  if (platforms.length === 0) return NextResponse.json({ error: 'Aucune plateforme sélectionnée' }, { status: 400 })

  const results: Record<string, { ok: boolean; id?: string; error?: string }> = {}

  for (const platform of platforms) {
    try {
      if (platform === 'linkedin') {
        const conn = await getConnection(user.id, 'linkedin')
        if (!conn) throw new Error('Compte LinkedIn non connecté.')
        const { id } = await publishText(conn.access_token, conn.external_id, text)
        results.linkedin = { ok: true, id }
      } else {
        results[platform] = { ok: false, error: 'Plateforme pas encore prise en charge.' }
      }
    } catch (e) {
      results[platform] = { ok: false, error: e instanceof Error ? e.message : String(e) }
    }
  }

  const anyOk = Object.values(results).some((r) => r.ok)
  return NextResponse.json({ success: anyOk, results }, { status: anyOk ? 200 : 502 })
}
