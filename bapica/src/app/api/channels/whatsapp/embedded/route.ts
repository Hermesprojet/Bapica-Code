import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { saveChannel } from '@/lib/channels/store'

const GRAPH = 'https://graph.facebook.com/v21.0'
const TABLE_MISSING_MSG =
  "Base de données non initialisée : exécutez bapica/supabase-schema.sql dans Supabase (SQL Editor), puis réessayez."

/**
 * WhatsApp Embedded Signup (Meta Cloud API) — connexion « en 1 clic » pour le client,
 * qui GARDE son numéro, SANS Twilio ni Facebook Developers.
 *
 * Le front (bouton « Connecter WhatsApp » + SDK Meta) obtient un `code` d'autorisation et
 * les identifiants du compte (phone_number_id, waba_id). Cette route :
 *   1. échange le `code` contre un jeton d'accès (business token) ;
 *   2. abonne le WABA du client au webhook de l'app ;
 *   3. (best effort) enregistre le numéro pour la Cloud API ;
 *   4. stocke la connexion (externalId = phone_number_id) → résolution du locataire au webhook.
 *
 * ÉCRIT À L'AVEUGLE. Prérequis prod (côté Bapica) : app Meta vérifiée avec WhatsApp + Embedded
 * Signup, et variables NEXT_PUBLIC_FACEBOOK_APP_ID / NEXT_PUBLIC_WHATSAPP_CONFIG_ID / FACEBOOK_APP_SECRET.
 */
export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  const appId = process.env.NEXT_PUBLIC_FACEBOOK_APP_ID
  const appSecret = process.env.FACEBOOK_APP_SECRET
  if (!appId || !appSecret) {
    return NextResponse.json(
      { error: 'Connexion Meta en cours de configuration (variables Meta manquantes côté serveur).' },
      { status: 503 },
    )
  }

  let body: any = {}
  try { body = await req.json() } catch { return NextResponse.json({ error: 'Requête invalide.' }, { status: 400 }) }

  const code = typeof body.code === 'string' ? body.code.trim() : ''
  const phoneNumberId = typeof body.phoneNumberId === 'string' ? body.phoneNumberId.trim() : ''
  const wabaId = typeof body.wabaId === 'string' ? body.wabaId.trim() : ''
  if (!code) return NextResponse.json({ error: 'Autorisation incomplète (code manquant).' }, { status: 400 })
  if (!phoneNumberId) return NextResponse.json({ error: 'Numéro WhatsApp non transmis par Meta.' }, { status: 400 })

  try {
    // 1. Échange du code contre un jeton d'accès (business token).
    const tokenRes = await fetch(
      `${GRAPH}/oauth/access_token?client_id=${encodeURIComponent(appId)}&client_secret=${encodeURIComponent(appSecret)}&code=${encodeURIComponent(code)}`,
      { signal: AbortSignal.timeout(12000) },
    )
    const tokenData = await tokenRes.json().catch(() => ({}))
    const accessToken = tokenData?.access_token
    if (!tokenRes.ok || !accessToken) {
      return NextResponse.json({ error: `Échange du code refusé par Meta : ${tokenData?.error?.message || 'erreur inconnue'}` }, { status: 400 })
    }

    // 2. Abonner le WABA du client au webhook de l'app (best effort).
    if (wabaId) {
      await fetch(`${GRAPH}/${encodeURIComponent(wabaId)}/subscribed_apps`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${accessToken}` },
        signal: AbortSignal.timeout(12000),
      }).catch(() => {})
    }

    // 3. Enregistrer le numéro pour la Cloud API (best effort ; PIN à 6 chiffres).
    await fetch(`${GRAPH}/${encodeURIComponent(phoneNumberId)}/register`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ messaging_product: 'whatsapp', pin: '000000' }),
      signal: AbortSignal.timeout(12000),
    }).catch(() => {})

    // 4. Récupérer le numéro affichable (best effort).
    let displayNumber = ''
    try {
      const infoRes = await fetch(`${GRAPH}/${encodeURIComponent(phoneNumberId)}?fields=display_phone_number`, {
        headers: { Authorization: `Bearer ${accessToken}` },
        signal: AbortSignal.timeout(8000),
      })
      const info = await infoRes.json().catch(() => ({}))
      displayNumber = info?.display_phone_number || ''
    } catch { /* ignore */ }

    // 5. Enregistrer la connexion (externalId = phone_number_id → résolution locataire au webhook).
    await saveChannel(user.id, 'whatsapp', {
      credentials: { accessToken, wabaId, phoneNumberId, via: 'cloud', displayNumber },
      externalId: phoneNumberId,
    })

    return NextResponse.json({ success: true, phoneNumberId, displayNumber })
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e)
    if (msg.includes('CHANNELS_TABLE_MISSING')) return NextResponse.json({ error: TABLE_MISSING_MSG }, { status: 400 })
    return NextResponse.json({ error: `Connexion Meta impossible : ${msg}` }, { status: 502 })
  }
}
