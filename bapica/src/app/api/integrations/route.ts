import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { getAvailableIntegrations } from '@/lib/integrations'
import { connectMethodFor } from '@/lib/integrations-connect'
import { saveConnection, listPlatforms, deleteConnection } from '@/lib/social/store'

/**
 * Connexions aux plateformes du client (Gmail, compta, banque, CRM…).
 * Stockage par client dans `social_connections` (service_role, RLS sans policy).
 *
 * GET    → { connected: string[] }
 * POST   { provider, apiKey } → enregistre la clé du client
 * DELETE { provider }         → déconnecte
 */
export async function GET(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  try {
    const connected = await listPlatforms(user.id)
    return NextResponse.json({ connected })
  } catch {
    return NextResponse.json({ connected: [] })
  }
}

export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  let body: any = {}
  try { body = await req.json() } catch { return NextResponse.json({ error: 'Requête invalide.' }, { status: 400 }) }

  const provider = typeof body.provider === 'string' ? body.provider.trim() : ''
  const apiKey = typeof body.apiKey === 'string' ? body.apiKey.trim() : ''

  const catalogIds = getAvailableIntegrations().map((i) => i.id as string)
  if (!provider || !catalogIds.includes(provider)) {
    return NextResponse.json({ error: 'Plateforme inconnue.' }, { status: 400 })
  }
  if (connectMethodFor(provider) !== 'api_key') {
    return NextResponse.json(
      { error: "Cette plateforme ne se connecte pas par clé API (OAuth ou intégration à venir)." },
      { status: 400 }
    )
  }
  if (!apiKey || apiKey.length < 8) {
    return NextResponse.json({ error: 'Clé API invalide (trop courte).' }, { status: 400 })
  }

  try {
    await saveConnection(user.id, provider, { accessToken: apiKey })
    return NextResponse.json({ success: true, provider })
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e)
    if (/does not exist|42P01/i.test(msg)) {
      return NextResponse.json(
        { error: 'Base non initialisée : exécutez supabase-schema.sql dans Supabase.' },
        { status: 400 }
      )
    }
    return NextResponse.json({ error: `Enregistrement impossible : ${msg}` }, { status: 500 })
  }
}

export async function DELETE(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  let body: any = {}
  try { body = await req.json() } catch { /* ignore */ }
  const provider = typeof body.provider === 'string' ? body.provider.trim() : ''
  if (!provider) return NextResponse.json({ error: 'Plateforme requise.' }, { status: 400 })
  try {
    await deleteConnection(user.id, provider)
    return NextResponse.json({ success: true })
  } catch (e) {
    return NextResponse.json({ error: String(e instanceof Error ? e.message : e) }, { status: 500 })
  }
}
