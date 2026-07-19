import { NextRequest, NextResponse } from 'next/server'
import { randomUUID } from 'crypto'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { saveChannel, getChannel, deleteChannel } from '@/lib/channels/store'

const TABLE_MISSING_MSG =
  "Base de données non initialisée : exécutez bapica/supabase-schema.sql dans Supabase (SQL Editor), puis réessayez."

/**
 * Connexion Telegram multi-client.
 * POST { token } — valide le jeton (getMe), génère un secret, l'enregistre dans
 *   channel_connections (scopé à l'utilisateur), puis setWebhook AVEC secret_token.
 * GET — état de la connexion Telegram de l'utilisateur.
 * DELETE — déconnecte (deleteWebhook + suppression en base).
 */
export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  let body: any = {}
  try { body = await req.json() } catch { return NextResponse.json({ error: 'Requête invalide.' }, { status: 400 }) }

  const token = typeof body.token === 'string' ? body.token.trim() : ''
  if (!token || !/^\d+:[\w-]{20,}$/.test(token)) {
    return NextResponse.json({ error: 'Jeton de bot invalide. Copiez le jeton fourni par @BotFather (format 123456:AA...).' }, { status: 400 })
  }

  const appUrl = process.env.NEXT_PUBLIC_APP_URL || ''
  if (!appUrl) {
    return NextResponse.json({ error: "NEXT_PUBLIC_APP_URL n'est pas configuré côté serveur." }, { status: 400 })
  }
  const webhookUrl = `${appUrl.replace(/\/$/, '')}/api/webhooks/messaging`

  try {
    // 1. Valider le jeton
    const me = await fetch(`https://api.telegram.org/bot${token}/getMe`).then((r) => r.json())
    if (!me?.ok) {
      return NextResponse.json({ error: 'Jeton refusé par Telegram. Vérifiez-le auprès de @BotFather.' }, { status: 400 })
    }
    const botUsername = me.result?.username || ''
    const secret = randomUUID()

    // 2. Enregistrer la connexion (avant de poser le webhook)
    try {
      await saveChannel(user.id, 'telegram', {
        credentials: { botToken: token },
        externalId: botUsername || null,
        webhookSecret: secret,
      })
    } catch (e) {
      const msg = String(e instanceof Error ? e.message : e)
      if (msg.includes('CHANNELS_TABLE_MISSING')) {
        return NextResponse.json({ error: TABLE_MISSING_MSG }, { status: 400 })
      }
      return NextResponse.json({ error: `Enregistrement impossible : ${msg}` }, { status: 500 })
    }

    // 3. Poser le webhook AVEC le secret (pour identifier ce client à la réception)
    const set = await fetch(
      `https://api.telegram.org/bot${token}/setWebhook?url=${encodeURIComponent(webhookUrl)}&secret_token=${encodeURIComponent(secret)}`
    ).then((r) => r.json())
    if (!set?.ok) {
      await deleteChannel(user.id, 'telegram').catch(() => {})
      return NextResponse.json({ error: `Échec de l'enregistrement du webhook : ${set?.description || 'erreur inconnue'}` }, { status: 502 })
    }

    return NextResponse.json({ success: true, botUsername })
  } catch (e) {
    return NextResponse.json({ error: `Erreur Telegram : ${String(e instanceof Error ? e.message : e)}` }, { status: 502 })
  }
}

export async function GET(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  try {
    const conn = await getChannel(user.id, 'telegram')
    return NextResponse.json({ connected: Boolean(conn), botUsername: conn?.external_id || '' })
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e)
    if (msg.includes('CHANNELS_TABLE_MISSING')) {
      return NextResponse.json({ connected: false, needsSetup: true })
    }
    return NextResponse.json({ connected: false })
  }
}

export async function DELETE(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  try {
    const conn = await getChannel(user.id, 'telegram')
    const botToken = (conn?.credentials as { botToken?: string } | undefined)?.botToken
    if (botToken) {
      await fetch(`https://api.telegram.org/bot${botToken}/deleteWebhook`).catch(() => {})
    }
    await deleteChannel(user.id, 'telegram')
    return NextResponse.json({ success: true })
  } catch (e) {
    return NextResponse.json({ error: String(e instanceof Error ? e.message : e) }, { status: 500 })
  }
}
