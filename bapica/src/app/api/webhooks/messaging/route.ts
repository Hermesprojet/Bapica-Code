import { NextRequest, NextResponse } from 'next/server'
import {
  handleWhatsAppWebhook, sendWhatsApp,
  handleTelegramWebhook, sendTelegram,
  handleMessengerWebhook, sendMessenger,
  handleTwilioWhatsApp,
  routeMessage, dispatchResponse,
  type IncomingMessage,
} from '@/lib/omnichannel'

/**
 * POST /api/webhooks/messaging — Webhook UNIQUE pour tous les canaux
 * 
 * WhatsApp, Telegram, Messenger → même endpoint.
 * Bapica détecte automatiquement la source et route.
 */
export async function POST(req: NextRequest) {
  try {
    const contentType = req.headers.get('content-type') || ''

    // Twilio (WhatsApp) envoie du form-urlencoded, pas du JSON.
    if (contentType.includes('x-www-form-urlencoded') || contentType.includes('multipart/form-data')) {
      const form = await req.formData()
      const params: Record<string, string> = {}
      form.forEach((v, k) => { params[k] = String(v) })
      const twMsg = handleTwilioWhatsApp(params)
      if (twMsg) {
        const { agentId, greeting } = routeMessage(twMsg)
        const quickReply = greeting || `Message reçu, je transfère à l'agent ${agentId}.`
        await dispatchResponse(twMsg, quickReply)
        if (!greeting) processMessageWithAgent(twMsg, agentId).catch(console.error)
      }
      // Twilio attend une réponse TwiML (200).
      return new Response('<Response></Response>', { status: 200, headers: { 'Content-Type': 'text/xml' } })
    }

    const body = await req.json()
    const platform = req.headers.get('x-messaging-platform') || detectPlatform(body)

    let msg: IncomingMessage | null = null

    switch (platform) {
      case 'whatsapp':
        msg = await handleWhatsAppWebhook(body)
        break
      case 'telegram':
        msg = await handleTelegramWebhook(body)
        break
      case 'messenger':
        msg = await handleMessengerWebhook(body)
        break
      default:
        // Auto-détection
        msg = await handleWhatsAppWebhook(body)
        if (!msg) msg = await handleTelegramWebhook(body)
        if (!msg) msg = await handleMessengerWebhook(body)
    }

    if (!msg) {
      return NextResponse.json({ received: true, status: 'no_text_message' })
    }

    // Router vers le bon agent
    const { agentId, greeting, confidence } = routeMessage(msg)

    // Réponse immédiate (le traitement IA suit en arrière-plan)
    const quickReply = greeting || `✅ Message reçu. Je transfère à l'agent **${agentId}** (${Math.round(confidence * 100)}% de pertinence).`
    
    // Envoyer la réponse rapide
    await dispatchResponse(msg, quickReply)

    // Lancer le traitement IA en arrière-plan (non bloquant pour le webhook)
    if (!greeting) {
      processMessageWithAgent(msg, agentId).catch(console.error)
    }

    return NextResponse.json({
      received: true,
      routed: { agentId, confidence },
      platform,
      replied: true,
    })
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 422 })
  }
}

/**
 * GET /api/webhooks/messaging — Vérification webhook (Facebook/Meta)
 */
export async function GET(req: NextRequest) {
  const params = req.nextUrl.searchParams
  const mode = params.get('hub.mode')
  const token = params.get('hub.verify_token')
  const challenge = params.get('hub.challenge')

  // Vérification Meta (WhatsApp + Messenger)
  if (mode === 'subscribe') {
    const verifyToken = process.env.WHATSAPP_VERIFY_TOKEN || process.env.MESSENGER_VERIFY_TOKEN || 'bapica_verify'
    if (token === verifyToken) {
      return new Response(challenge, { status: 200 })
    }
    return new Response('Forbidden', { status: 403 })
  }

  return NextResponse.json({ status: 'ok', platforms: ['whatsapp', 'telegram', 'messenger'] })
}

// ─── HELPERS ───────────────────────────────────────────────

function detectPlatform(body: any): string {
  if (body?.entry?.[0]?.changes?.[0]?.value?.messages) return 'whatsapp'
  if (body?.entry?.[0]?.messaging) return 'messenger'
  if (body?.message?.chat) return 'telegram'
  return 'unknown'
}

/**
 * Traite le message avec l'agent Bapica approprié
 * (appelé en arrière-plan, non-bloquant pour le webhook)
 */
async function processMessageWithAgent(msg: IncomingMessage, agentId: string) {
  try {
    const response = await fetch(`${process.env.NEXT_PUBLIC_APP_URL}/api/demo-chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        agentId,
        message: msg.text,
        history: [],
      }),
    })

    if (!response.ok) return

    const data = await response.json()
    const reply = data.response || data.message || 'Désolé, je n\'ai pas pu traiter votre demande.'

    await dispatchResponse(msg, reply)
  } catch (e) {
    console.error('Agent processing failed:', e)
    await dispatchResponse(msg, '⚠️ Désolé, une erreur est survenue. Veuillez réessayer dans quelques instants.')
  }
}
