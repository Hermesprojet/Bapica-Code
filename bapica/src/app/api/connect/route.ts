import { NextRequest, NextResponse } from 'next/server'
import { discoverPlatform, detectAuth, learnFromExample, routeWebhook } from '@/lib/universal-connector'

/**
 * POST /api/connect/discover — Tente de découvrir automatiquement un SaaS
 */
export async function POST(req: NextRequest) {
  try {
    const { url } = await req.json()
    if (!url) return NextResponse.json({ error: 'URL requise' }, { status: 400 })

    const discovery = await discoverPlatform(url)
    const auth = await detectAuth(url)

    return NextResponse.json({
      discovered: {
        ...discovery,
        auth,
        endpointCount: discovery.endpoints?.length || 0,
        confidence: discovery.endpoints?.length ? 'high' : 'medium',
        message: discovery.endpoints?.length
          ? `✅ ${discovery.endpoints.length} endpoints découverts automatiquement`
          : '⚠️ Aucun endpoint standard détecté. Utilisez le mode apprentissage (copier-coller une requête Postman).',
      },
      nextSteps: discovery.endpoints?.length
        ? ['Configurer les credentials', 'Tester une requête', 'Connecter aux agents']
        : ['Fournir un exemple de requête', 'Spécifier manuellement les endpoints'],
    })
  } catch (e) {
    return NextResponse.json({ error: 'Échec de la découverte', details: String(e) }, { status: 422 })
  }
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
