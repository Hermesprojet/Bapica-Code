import { NextRequest, NextResponse } from 'next/server'
import Anthropic from '@anthropic-ai/sdk'

// CORS
function corsHeaders(origin: string | null) {
  return {
    'Access-Control-Allow-Origin': origin || '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
  }
}

export async function OPTIONS(req: NextRequest) {
  return NextResponse.json({}, { headers: corsHeaders(req.headers.get('origin')) })
}

// Route de démonstration publique (sans compte) pour la page d'accueil.
// POST /api/demo-chat — Body: { message, history }
//
// Garde-fous côté serveur (indépendants du client) :
// - 3 messages utilisateur maximum par conversation
// - longueur de message plafonnée
// - réponses courtes (max_tokens réduit) sur le modèle économique

const MAX_USER_MESSAGES = 3
const MAX_MESSAGE_LENGTH = 500

interface HistoryMessage {
  role: 'user' | 'assistant'
  content: string
}

const DEMO_SYSTEM_PROMPT = [
  "Tu es « Léo », l'agent général de Bapica, une plateforme d'agents IA pour PME et indépendants (prospection, support client, contenu, comptabilité, recrutement, standard téléphonique...).",
  "Tu discutes avec un visiteur du site en mode démonstration : il teste la qualité des réponses avant de créer un compte.",
  "Réponds à sa question de façon réellement utile et concrète, comme un excellent consultant : c'est la meilleure démonstration possible.",
  "Si sa question touche à un métier couvert par un agent Bapica (trouver des clients, support, contenu, factures, recrutement...), mentionne naturellement en une phrase l'agent concerné.",
  "Détecte automatiquement la langue du visiteur et réponds dans cette même langue, quelle qu'elle soit.",
  'Ton professionnel, courtois et sobre. Pas d\'émojis. Pas de mise en forme Markdown (pas de #, de **, ni de symboles de liste).',
  'Réponses courtes : 4 à 6 phrases maximum.',
  "Ne demande jamais d'informations personnelles ou sensibles.",
].join('\n')

export async function POST(req: NextRequest) {
  try {
    const { message, history } = await req.json()

    if (!message || typeof message !== 'string' || !message.trim()) {
      return NextResponse.json({ error: 'Message requis' }, { status: 400, headers: corsHeaders(req.headers.get('origin')) })
    }
    if (message.length > MAX_MESSAGE_LENGTH) {
      return NextResponse.json(
        { error: `Message trop long (max ${MAX_MESSAGE_LENGTH} caractères).` },
        { status: 400, headers: corsHeaders(req.headers.get('origin')) }
      )
    }

    // Nettoie l'historique et applique la limite serveur de la démo.
    const cleanHistory: HistoryMessage[] = Array.isArray(history)
      ? history
          .filter(
            (m: HistoryMessage) =>
              (m?.role === 'user' || m?.role === 'assistant') &&
              typeof m?.content === 'string' &&
              m.content.trim().length > 0
          )
          .slice(-2 * MAX_USER_MESSAGES)
          .map((m: HistoryMessage) => ({
            role: m.role,
            content: m.content.slice(0, MAX_MESSAGE_LENGTH),
          }))
      : []

    const userTurns = cleanHistory.filter((m) => m.role === 'user').length
    if (userTurns >= MAX_USER_MESSAGES) {
      return NextResponse.json(
        {
          limitReached: true,
          response:
            'Vous avez utilisé vos messages de démonstration. Créez un compte gratuit pour continuer la conversation avec vos agents.',
        },
        { status: 200, headers: corsHeaders(req.headers.get('origin')) }
      )
    }

    const apiKey = process.env.ANTHROPIC_API_KEY
    if (!apiKey) {
      return NextResponse.json(
        { error: 'Démo momentanément indisponible.' },
        { status: 503, headers: corsHeaders(req.headers.get('origin')) }
      )
    }

    const client = new Anthropic({ apiKey })
    const completion = await client.messages.create({
      model: 'claude-haiku-4-5',
      max_tokens: 400,
      system: DEMO_SYSTEM_PROMPT,
      messages: [
        ...cleanHistory,
        { role: 'user' as const, content: message.trim() },
      ],
    })

    const text = completion.content
      .filter((b): b is Anthropic.TextBlock => b.type === 'text')
      .map((b) => b.text)
      .join('\n')
      .trim()

    const remaining = MAX_USER_MESSAGES - userTurns - 1
    return NextResponse.json({ response: text, remaining }, { headers: corsHeaders(req.headers.get('origin')) })
  } catch (error) {
    console.error('Demo chat error:', error)
    return NextResponse.json(
      { error: 'Démo momentanément indisponible.' },
      { status: 500, headers: corsHeaders(req.headers.get('origin')) }
    )
  }
}
