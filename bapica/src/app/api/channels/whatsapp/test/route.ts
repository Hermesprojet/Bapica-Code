import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { sendTwilioWhatsAppDetailed } from '@/lib/omnichannel'
import { getChannel } from '@/lib/channels/store'

/**
 * POST /api/channels/whatsapp/test — envoie un WhatsApp de test via Twilio et
 * renvoie l'erreur EXACTE de Twilio en cas d'échec (diagnostic de configuration).
 * Auth : Bearer Supabase. Corps : { to } (numéro E.164, ex : +32465474183).
 */
export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  let body: any = {}
  try { body = await req.json() } catch { return NextResponse.json({ error: 'Requête invalide.' }, { status: 400 }) }

  const to = typeof body.to === 'string' ? body.to.trim() : ''
  if (!to || !/^\+?\d{6,15}$/.test(to.replace(/[\s.-]/g, ''))) {
    return NextResponse.json({ error: 'Numéro invalide. Format attendu : +32465474183' }, { status: 400 })
  }

  // Identifiants Twilio DU CLIENT (connexion in-app), si présents.
  let creds: { sid?: string; auth?: string; from?: string } | undefined
  try {
    const conn = await getChannel(user.id, 'whatsapp')
    const c = conn?.credentials as { accountSid?: string; authToken?: string; fromNumber?: string } | undefined
    if (c?.accountSid) creds = { sid: c.accountSid, auth: c.authToken, from: c.fromNumber }
  } catch { /* repli sur variables globales */ }

  const result = await sendTwilioWhatsAppDetailed(
    to.replace(/[\s.-]/g, ''),
    'Test Bapica : si vous recevez ce message, la connexion WhatsApp fonctionne.',
    creds
  )

  return NextResponse.json(result, { status: result.ok ? 200 : 502 })
}
