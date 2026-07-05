import { NextRequest, NextResponse } from 'next/server'
import Anthropic from '@anthropic-ai/sdk'
import { getAgentById } from '@/lib/agents'

// Route de démonstration publique (sans compte) pour la page d'accueil.
// POST /api/demo-chat — Body: { agentId, message, history }

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

const MAX_USER_MESSAGES = 3
const MAX_MESSAGE_LENGTH = 500

interface HistoryMessage {
  role: 'user' | 'assistant'
  content: string
}

function buildSystemPrompt(agentId: string): string {
  const agent = getAgentById(agentId)
  
  if (!agent) {
    // Fallback: Léo généraliste
    return [
      "Tu es « Léo », l'agent général de Bapica, une plateforme d'agents IA pour PME et indépendants (prospection, support client, contenu, comptabilité, recrutement, standard téléphonique...).",
      "Tu discutes avec un visiteur du site en mode démonstration.",
      "Réponds à sa question de façon réellement utile et concrète.",
      "Détecte automatiquement la langue du visiteur et réponds dans cette même langue, quelle qu'elle soit.",
      "Ton professionnel, courtois et sobre. Pas d'émojis. Pas de mise en forme Markdown.",
      "Réponses courtes : 4 à 6 phrases maximum.",
    ].join('\n')
  }

  // Construire un prompt spécifique à l'agent
  const lines = [
    `Tu es « ${agent.persona} », l'${agent.name} de Bapica. Tes compétences : ${agent.description}`,
  ]

  // Ajouter le contexte de coordination pour Léo
  if (agent.id === 'general') {
    lines.push(
      "Tu es l'agent coordinateur. Tu peux faire appel aux autres agents spécialisés de Bapica : Sofia (Support Client), Camille (Contenu/SEO), Marc (Commercial), Nadia (Closer téléphonique), Hugo (Standard téléphonique), Claire (Comptabilité), Maya (Vidéo), Yanis (Recrutement), Inès (Juridique), Lina (Tendances), Tom (Analytics).",
      "Si un visiteur a besoin d'une expertise spécifique, mentionne l'agent concerné et ce qu'il peut faire pour lui.",
      "Tu coordonnes l'équipe : tu analyses la demande, identifies les agents pertinents, et orientes le visiteur."
    )
  }

  lines.push(
    "Tu discutes avec un visiteur du site en mode démonstration.",
    "Réponds à sa question de façon réellement utile et concrète, comme un expert.",
    "Si sa question touche à un domaine couvert par un autre agent Bapica, mentionne-le naturellement.",
    "Détecte automatiquement la langue du visiteur et réponds dans cette même langue, quelle qu'elle soit.",
    "Ton professionnel, courtois et sobre. Pas d'émojis. Pas de mise en forme Markdown.",
    "Réponses courtes : 4 à 6 phrases maximum.",
    "Ne demande jamais d'informations personnelles ou sensibles.",
  )

  return lines.join('\n')
}

export async function POST(req: NextRequest) {
  try {
    const { agentId, message, history } = await req.json()

    if (!message || typeof message !== 'string' || !message.trim()) {
      return NextResponse.json({ error: 'Message requis' }, { status: 400, headers: corsHeaders(req.headers.get('origin')) })
    }
    if (message.length > MAX_MESSAGE_LENGTH) {
      return NextResponse.json(
        { error: `Message trop long (max ${MAX_MESSAGE_LENGTH} caractères).` },
        { status: 400, headers: corsHeaders(req.headers.get('origin')) }
      )
    }

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
        { limitReached: true, response: 'Vous avez utilisé vos messages de démonstration. Créez un compte gratuit pour continuer.' },
        { status: 200, headers: corsHeaders(req.headers.get('origin')) }
      )
    }

    const apiKey = process.env.ANTHROPIC_API_KEY
    if (!apiKey) {
      return NextResponse.json({ error: 'Démo momentanément indisponible.' }, { status: 503, headers: corsHeaders(req.headers.get('origin')) })
    }

    const agent = getAgentById(agentId || 'general')
    const systemPrompt = buildSystemPrompt(agentId || 'general')
    
    // Utiliser le modèle approprié (Haiku pour simple, Sonnet pour complexe)
    const model = agent?.model === 'claude-sonnet-4' ? 'claude-sonnet-4-6' : 'claude-haiku-4-5'
    const maxTokens = agent?.maxTokens ? Math.min(agent.maxTokens, 600) : 400

    const client = new Anthropic({ apiKey })
    const completion = await client.messages.create({
      model,
      max_tokens: maxTokens,
      system: systemPrompt,
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
    return NextResponse.json({ response: text, remaining, agent: agent?.persona || 'Léo' }, { headers: corsHeaders(req.headers.get('origin')) })
  } catch (error) {
    console.error('Demo chat error:', error)
    return NextResponse.json({ error: 'Démo momentanément indisponible.' }, { status: 500, headers: corsHeaders(req.headers.get('origin')) })
  }
}
