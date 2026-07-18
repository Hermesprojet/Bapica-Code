import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'

/**
 * GET /api/channels/status — indique quels canaux de messagerie sont configurés.
 *
 * Ne renvoie JAMAIS la valeur des jetons : uniquement des booléens attestant leur
 * présence côté serveur (variables d'environnement Vercel). Auth : Bearer Supabase.
 */
export async function GET(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) {
    return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  }

  const appUrl = process.env.NEXT_PUBLIC_APP_URL || ''

  return NextResponse.json({
    channels: {
      whatsapp: Boolean(process.env.WHATSAPP_TOKEN && process.env.WHATSAPP_PHONE_ID),
      telegram: Boolean(process.env.TELEGRAM_BOT_TOKEN),
      messenger: Boolean(process.env.MESSENGER_PAGE_TOKEN),
    },
    webhookUrl: appUrl ? `${appUrl.replace(/\/$/, '')}/api/webhooks/messaging` : null,
    appUrlConfigured: Boolean(appUrl),
  })
}
