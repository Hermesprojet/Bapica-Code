import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { saveConnection, getConnection, deleteConnection } from '@/lib/social/store'

/**
 * Connexion d'une boutique Shopify via l'API Admin + un jeton d'app privée
 * (Admin Shopify → Paramètres → Apps → Développer des apps → jeton Admin API, shpat_...).
 * Permet à Camille de lire et de modifier fiches produits/pages, avec validation.
 */
function normalizeShop(input: string): string {
  let s = input.trim().toLowerCase().replace(/^https?:\/\//, '').replace(/\/.*$/, '')
  if (s && !s.includes('.')) s = `${s}.myshopify.com`
  return s
}

export async function GET(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  try {
    const conn = await getConnection(user.id, 'shopify')
    if (!conn) return NextResponse.json({ connected: false })
    let meta: { shop?: string } = {}
    try { meta = JSON.parse((conn as { external_id?: string }).external_id || '{}') } catch { /* ignore */ }
    return NextResponse.json({ connected: true, shop: meta.shop || '' })
  } catch {
    return NextResponse.json({ connected: false })
  }
}

export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  let b: any = {}
  try { b = await req.json() } catch { return NextResponse.json({ error: 'Requête invalide.' }, { status: 400 }) }

  const shop = normalizeShop(String(b.shop || ''))
  const accessToken = String(b.accessToken || '').trim()
  if (!shop || !/\.myshopify\.com$/.test(shop)) {
    return NextResponse.json({ error: 'Domaine de boutique invalide (ex : ma-boutique.myshopify.com).' }, { status: 400 })
  }
  if (!accessToken) {
    return NextResponse.json({ error: "Jeton d'accès Admin API requis (shpat_...)." }, { status: 400 })
  }

  try {
    const res = await fetch(`https://${shop}/admin/api/2024-10/shop.json`, {
      headers: { 'X-Shopify-Access-Token': accessToken, Accept: 'application/json' },
      signal: AbortSignal.timeout(12000),
    })
    if (!res.ok) {
      return NextResponse.json({ error: `Shopify a refusé la connexion (HTTP ${res.status}). Vérifiez le domaine et le jeton.` }, { status: 400 })
    }
  } catch (e) {
    return NextResponse.json({ error: `Boutique injoignable — ${String(e instanceof Error ? e.message : e)}` }, { status: 400 })
  }

  try {
    await saveConnection(user.id, 'shopify', { accessToken, externalId: JSON.stringify({ shop }) })
    return NextResponse.json({ success: true, shop })
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
    await deleteConnection(user.id, 'shopify')
    return NextResponse.json({ success: true })
  } catch (e) {
    return NextResponse.json({ error: String(e instanceof Error ? e.message : e) }, { status: 500 })
  }
}
