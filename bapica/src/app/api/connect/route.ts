import { NextRequest, NextResponse } from 'next/server'
import { discoverPlatform, detectAuth, learnFromExample, routeWebhook } from '@/lib/universal-connector'
import { generateConsentRequest, formatConsentMessage, recordConsent, hasConsent, type UserConsent } from '@/lib/consent-manager'

/**
 * POST /api/connect/discover — Découverte + demande de consentement
 */
export async function POST(req: NextRequest) {
  try {
    const { url, userId, action } = await req.json()

    // Si c'est une demande de consentement explicite
    if (action === 'consent' && userId && url) {
      const consentGranted = req.nextUrl.searchParams.get('grant') === 'true'
      
      if (consentGranted) {
        const consent: UserConsent = {
          userId,
          platformName: new URL(url).hostname,
          platformUrl: url,
          granted: true,
          grantedAt: new Date().toISOString(),
          scope: ['read', 'write'],
          riskLevel: 'medium',
        }
        recordConsent(consent)
        return NextResponse.json({ consented: true, message: '✅ Connexion autorisée' })
      } else {
        return NextResponse.json({ consented: false, message: '❌ Connexion refusée' })
      }
    }

    // Sinon, découvrir la plateforme et générer une demande de consentement
    if (!url) return NextResponse.json({ error: 'URL requise' }, { status: 400 })

    const discovery = await discoverPlatform(url)
    const auth = await detectAuth(url)
    const platformName = discovery.name || new URL(url).hostname
    const category = guessCategory(url, discovery)

    // Générer la demande de consentement
    const consentRequest = generateConsentRequest({ name: platformName, url, category })
    const message = formatConsentMessage(consentRequest)

    // Si userId fourni, vérifier s'il a déjà consenti
    const alreadyConsented = userId ? hasConsent(userId, platformName) : false

    return NextResponse.json({
      discovered: {
        ...discovery,
        auth,
        endpointCount: discovery.endpoints?.length || 0,
        category,
        alreadyConsented,
      },
      consentRequired: !alreadyConsented,
      consentRequest: alreadyConsented ? null : {
        ...consentRequest,
        message,
        actions: {
          grant: `/api/connect?action=consent&grant=true&url=${encodeURIComponent(url)}`,
          deny: `/api/connect?action=consent&grant=false&url=${encodeURIComponent(url)}`,
        },
      },
      nextSteps: alreadyConsented
        ? ['✅ Déjà connecté — utilisation immédiate']
        : ['📋 Lire la demande de consentement', '✅ Accepter ou ❌ Refuser'],
    })
  } catch (e) {
    return NextResponse.json({ error: 'Échec', details: String(e) }, { status: 422 })
  }
}

function guessCategory(url: string, discovery: any): string {
  const u = url.toLowerCase()
  if (u.includes('mail') || u.includes('slack') || u.includes('whatsapp')) return 'Communication'
  if (u.includes('stripe') || u.includes('compta') || u.includes('factur') || u.includes('pennylane')) return 'Finance'
  if (u.includes('crm') || u.includes('hubspot') || u.includes('salesforce')) return 'CRM'
  if (u.includes('twitter') || u.includes('linkedin') || u.includes('facebook')) return 'Social'
  if (u.includes('drive') || u.includes('dropbox') || u.includes('onedrive')) return 'Cloud'
  if (u.includes('shopify') || u.includes('woocommerce')) return 'Ecommerce'
  return 'Autre'
}

/**
 * POST /api/connect/learn — Apprend par exemples (copier-coller Postman)
 */
export async function PUT(req: NextRequest) {
  try {
    const { example } = await req.json()
    if (!example) return NextResponse.json({ error: 'Exemple requis' }, { status: 400 })

    const learned = learnFromExample(example)
    if (!learned) return NextResponse.json({ error: 'Format non reconnu' }, { status: 422 })

    return NextResponse.json({
      learned,
      suggestions: [
        `Méthode: ${learned.method}`,
        `URL pattern: ${learned.url.replace(/\/[^\/]+$/, '/{id}')}`,
        `Headers détectés: ${Object.keys(learned.headers).join(', ')}`,
      ],
    })
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 422 })
  }
}

/**
 * POST /api/webhooks/receive — Webhook Inbox Universel
 * Reçoit TOUS les webhooks, l'IA route vers le bon agent
 */
export async function PATCH(req: NextRequest) {
  try {
    const payload = await req.json()
    const source = req.headers.get('x-webhook-source') || 'unknown'
    const { agent, confidence } = routeWebhook(payload)

    return NextResponse.json({
      received: true,
      routed: { agent, confidence },
      processing: confidence > 0.3 ? 'auto' : 'manual_review',
      message: confidence > 0.3
        ? `✅ Routé vers l'agent ${agent}`
        : '⚠️ Source non reconnue — l\'IA va analyser ce webhook',
    })
  } catch {
    return NextResponse.json({ received: true, routed: { agent: 'general', confidence: 0 } })
  }
}
