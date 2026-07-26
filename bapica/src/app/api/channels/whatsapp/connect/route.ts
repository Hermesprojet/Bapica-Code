import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { saveChannel, getChannel, deleteChannel } from '@/lib/channels/store'

const TABLE_MISSING_MSG =
  "Base de données non initialisée : exécutez bapica/supabase-schema.sql dans Supabase (SQL Editor), puis réessayez."

/**
 * Connexion WhatsApp multi-client via Twilio — SANS variable Vercel ni redéploiement.
 * Le client colle son Account SID + Auth Token + numéro WhatsApp Twilio ; Bapica valide,
 * stocke les identifiants (scopés à l'utilisateur) et résout le locataire à la réception
 * via l'AccountSid présent dans chaque webhook Twilio (externalId = accountSid).
 *
 * POST { accountSid, authToken, fromNumber } — valide (appel API Twilio) puis enregistre.
 * GET    — état de la connexion.
 * DELETE — déconnecte.
 */
export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  let body: any = {}
  try { body = await req.json() } catch { return NextResponse.json({ error: 'Requête invalide.' }, { status: 400 }) }

  const accountSid = typeof body.accountSid === 'string' ? body.accountSid.trim() : ''
  const authToken = typeof body.authToken === 'string' ? body.authToken.trim() : ''
  const fromNumber = typeof body.fromNumber === 'string' ? body.fromNumber.trim().replace(/^whatsapp:/i, '') : ''

  if (!/^AC[0-9a-zA-Z]{30,}$/.test(accountSid)) {
    return NextResponse.json({ error: "Account SID invalide (il commence par « AC »). Copiez-le depuis la console Twilio." }, { status: 400 })
  }
  if (authToken.length < 20) {
    return NextResponse.json({ error: 'Auth Token invalide. Copiez-le depuis la console Twilio.' }, { status: 400 })
  }
  if (!/^\+?\d{6,15}$/.test(fromNumber)) {
    return NextResponse.json({ error: 'Numéro WhatsApp invalide (format international, ex : +14155238886).' }, { status: 400 })
  }

  // 1. Valider les identifiants auprès de Twilio (lecture du compte).
  try {
    const res = await fetch(`https://api.twilio.com/2010-04-01/Accounts/${accountSid}.json`, {
      headers: { Authorization: 'Basic ' + Buffer.from(`${accountSid}:${authToken}`).toString('base64') },
      signal: AbortSignal.timeout(10000),
    })
    if (!res.ok) {
      return NextResponse.json({ error: 'Identifiants refusés par Twilio. Vérifiez l’Account SID et l’Auth Token.' }, { status: 400 })
    }
  } catch (e) {
    return NextResponse.json({ error: `Impossible de joindre Twilio : ${String(e instanceof Error ? e.message : e)}` }, { status: 502 })
  }

  // 2. Enregistrer la connexion (externalId = accountSid → résolution du locataire au webhook).
  try {
    await saveChannel(user.id, 'whatsapp', {
      credentials: { accountSid, authToken, fromNumber, via: 'twilio' },
      externalId: accountSid,
    })
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e)
    if (msg.includes('CHANNELS_TABLE_MISSING')) return NextResponse.json({ error: TABLE_MISSING_MSG }, { status: 400 })
    return NextResponse.json({ error: `Enregistrement impossible : ${msg}` }, { status: 500 })
  }

  return NextResponse.json({ success: true, fromNumber })
}

export async function GET(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  try {
    const conn = await getChannel(user.id, 'whatsapp')
    const creds = (conn?.credentials as { fromNumber?: string; displayNumber?: string; via?: string } | undefined) || undefined
    return NextResponse.json({
      connected: !!conn,
      fromNumber: creds?.fromNumber || creds?.displayNumber || '',
      via: creds?.via || '',
    })
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e)
    if (msg.includes('CHANNELS_TABLE_MISSING')) return NextResponse.json({ connected: false, needsSetup: true })
    return NextResponse.json({ connected: false })
  }
}

export async function DELETE(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  try { await deleteChannel(user.id, 'whatsapp') } catch { /* ignore */ }
  return NextResponse.json({ success: true })
}
