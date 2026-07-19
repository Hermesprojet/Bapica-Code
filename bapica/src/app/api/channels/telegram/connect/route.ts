import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'

/**
 * POST /api/channels/telegram/connect — connexion Telegram « en 1 clic ».
 * Corps : { token } (jeton BotFather). Valide le token (getMe) puis enregistre
 * automatiquement le webhook (setWebhook) vers /api/webhooks/messaging.
 * Auth : Bearer Supabase.
 */
export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) {
    return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  }

  let body: any = {}
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Requête invalide.' }, { status: 400 })
  }

  const token = typeof body.token === 'string' ? body.token.trim() : ''
  if (!token || !/^\d+:[\w-]{20,}$/.test(token)) {
    return NextResponse.json(
      { error: 'Jeton de bot invalide. Copiez le jeton fourni par @BotFather (format 123456:AA...).' },
      { status: 400 }
    )
  }

  const appUrl = process.env.NEXT_PUBLIC_APP_URL || ''
  if (!appUrl) {
    return NextResponse.json(
      { error: "NEXT_PUBLIC_APP_URL n'est pas configuré côté serveur — impossible de construire l'URL de webhook." },
      { status: 400 }
    )
  }
  const webhookUrl = `${appUrl.replace(/\/$/, '')}/api/webhooks/messaging`

  try {
    // 1. Valider le jeton
    const me = await fetch(`https://api.telegram.org/bot${token}/getMe`).then((r) => r.json())
    if (!me?.ok) {
      return NextResponse.json({ error: 'Jeton refusé par Telegram. Vérifiez-le auprès de @BotFather.' }, { status: 400 })
    }

    // 2. Enregistrer le webhook automatiquement
    const set = await fetch(
      `https://api.telegram.org/bot${token}/setWebhook?url=${encodeURIComponent(webhookUrl)}`
    ).then((r) => r.json())
    if (!set?.ok) {
      return NextResponse.json({ error: `Échec de l'enregistrement du webhook : ${set?.description || 'erreur inconnue'}` }, { status: 502 })
    }

    return NextResponse.json({ success: true, botUsername: me.result?.username || '', webhookUrl })
  } catch (e) {
    return NextResponse.json({ error: `Erreur Telegram : ${String(e instanceof Error ? e.message : e)}` }, { status: 502 })
  }
}
