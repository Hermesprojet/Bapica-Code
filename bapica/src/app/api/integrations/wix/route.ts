import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { saveConnection, getConnection, deleteConnection } from '@/lib/social/store'

/**
 * Connexion d'un site Wix via l'API REST Wix (clé API de compte + Site ID).
 * Auth : en-tête Authorization (clé API) + wix-site-id.
 * ⚠️ L'API Wix est plus restrictive : la lecture/écriture SEO dépend des permissions de
 * la clé et du type de site. La connexion donne accès aux endpoints autorisés ; certaines
 * modifications peuvent rester indisponibles côté Wix.
 */
export async function GET(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  try {
    const conn = await getConnection(user.id, 'wix')
    if (!conn) return NextResponse.json({ connected: false })
    let meta: { siteId?: string } = {}
    try { meta = JSON.parse((conn as { external_id?: string }).external_id || '{}') } catch { /* ignore */ }
    return NextResponse.json({ connected: true, siteId: meta.siteId || '' })
  } catch {
    return NextResponse.json({ connected: false })
  }
}

export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  let b: any = {}
  try { b = await req.json() } catch { return NextResponse.json({ error: 'Requête invalide.' }, { status: 400 }) }

  const apiKey = String(b.apiKey || '').trim()
  const siteId = String(b.siteId || '').trim()
  if (!apiKey || !siteId) {
    return NextResponse.json({ error: 'Clé API Wix et Site ID requis.' }, { status: 400 })
  }

  // Vérifie via un endpoint léger (propriétés du site).
  try {
    const res = await fetch('https://www.wixapis.com/site-properties/v4/properties', {
      headers: { Authorization: apiKey, 'wix-site-id': siteId, Accept: 'application/json' },
      signal: AbortSignal.timeout(12000),
    })
    if (!res.ok && res.status !== 404) {
      const txt = await res.text().catch(() => '')
      return NextResponse.json(
        { error: `Wix a refusé la connexion (HTTP ${res.status}). Vérifiez la clé API et le Site ID. ${txt.slice(0, 200)}` },
        { status: 400 }
      )
    }
  } catch (e) {
    return NextResponse.json({ error: `Wix injoignable — ${String(e instanceof Error ? e.message : e)}` }, { status: 400 })
  }

  try {
    await saveConnection(user.id, 'wix', { accessToken: apiKey, externalId: JSON.stringify({ siteId }) })
    return NextResponse.json({ success: true, siteId })
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e)
    if (/does not exist|42P01/i.test(msg)) {
      return NextResponse.json({ error: 'Base non initialisée : exécutez supabase-schema.sql.' }, { status: 400 })
    }
    return NextResponse.json({ error: `Enregistrement impossible : ${msg}` }, { status: 500 })
  }
}

export async function DELETE(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  try {
    await deleteConnection(user.id, 'wix')
    return NextResponse.json({ success: true })
  } catch (e) {
    return NextResponse.json({ error: String(e instanceof Error ? e.message : e) }, { status: 500 })
  }
}
