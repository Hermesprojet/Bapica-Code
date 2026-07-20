import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { getAvailableIntegrations } from '@/lib/integrations'
import { connectMethodFor } from '@/lib/integrations-connect'
import { saveConnection, listConnections, deleteConnection } from '@/lib/social/store'

// Préfixe des plateformes ajoutées manuellement par le client (hors catalogue).
const CUSTOM_PREFIX = 'custom:'

function slugify(s: string): string {
  return s
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '') // retire les accents
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40)
}

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
    const rows = await listConnections(user.id)
    const connected = rows.map((r) => r.platform)
    // Plateformes hors catalogue ajoutées par le client : métadonnées en JSON dans external_id.
    const custom = rows
      .filter((r) => r.platform.startsWith(CUSTOM_PREFIX))
      .map((r) => {
        let meta: { name?: string; baseUrl?: string; category?: string } = {}
        try { meta = JSON.parse(r.external_id || '{}') } catch { /* ignore */ }
        return {
          platform: r.platform,
          name: meta.name || r.platform.slice(CUSTOM_PREFIX.length),
          baseUrl: meta.baseUrl || '',
          category: meta.category || 'Autre',
        }
      })
    return NextResponse.json({ connected, custom })
  } catch {
    return NextResponse.json({ connected: [], custom: [] })
  }
}

export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  let body: any = {}
  try { body = await req.json() } catch { return NextResponse.json({ error: 'Requête invalide.' }, { status: 400 }) }

  const provider = typeof body.provider === 'string' ? body.provider.trim() : ''
  const apiKey = typeof body.apiKey === 'string' ? body.apiKey.trim() : ''

  // ── Plateforme hors catalogue (app, banque, logiciel métier…) ──
  if (body.custom === true) {
    const name = typeof body.name === 'string' ? body.name.trim() : ''
    const baseUrl = typeof body.baseUrl === 'string' ? body.baseUrl.trim() : ''
    const category = typeof body.category === 'string' ? body.category.trim() : 'Autre'
    const authType = ['bearer', 'basic', 'header', 'raw'].includes(body.authType) ? body.authType : 'bearer'
    const headerName = typeof body.headerName === 'string' ? body.headerName.trim() : ''
    const authUser = typeof body.authUser === 'string' ? body.authUser.trim() : ''
    const slug = slugify(name)

    if (!name || !slug) {
      return NextResponse.json({ error: 'Nom de la plateforme requis.' }, { status: 400 })
    }
    if (!apiKey || apiKey.length < 4) {
      return NextResponse.json({ error: 'Clé ou identifiant d’accès invalide (trop court).' }, { status: 400 })
    }
    if (baseUrl && !/^https?:\/\//i.test(baseUrl)) {
      return NextResponse.json({ error: 'L’URL de l’API doit commencer par https://' }, { status: 400 })
    }

    try {
      await saveConnection(user.id, `${CUSTOM_PREFIX}${slug}`, {
        accessToken: apiKey,
        externalId: JSON.stringify({ name, baseUrl, category, authType, headerName, user: authUser }),
      })
      return NextResponse.json({ success: true, provider: `${CUSTOM_PREFIX}${slug}`, name })
    } catch (e) {
      const msg = String(e instanceof Error ? e.message : e)
      if (/does not exist|42P01/i.test(msg)) {
        return NextResponse.json({ error: 'Base non initialisée : exécutez supabase-schema.sql dans Supabase.' }, { status: 400 })
      }
      return NextResponse.json({ error: `Enregistrement impossible : ${msg}` }, { status: 500 })
    }
  }

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
