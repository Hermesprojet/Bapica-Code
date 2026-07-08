import { NextRequest, NextResponse } from 'next/server'
import Anthropic from '@anthropic-ai/sdk'
import { getAgentById } from '@/lib/agents'
import { buildFablePrompt, routeModel, type ModelTier } from '@/lib/fable-routing'

// Route de démonstration publique (sans compte)
// POST /api/demo-chat — Body: { agentId, message, history }
// Patterns Claude Fable 5 appliqués : prose naturelle, natural memory, product knowledge

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
    return [
      "Tu es Léo, l'agent général de Bapica — une plateforme qui donne aux PME une équipe d'agents IA spécialisés (prospection, support, contenu, compta, téléphone, recrutement, juridique, vidéo, analytics, scaling).",
      "Tu discutes avec un visiteur en mode démonstration. Réponds de façon utile et concrète.",
      "Parle en prose naturelle — pas de listes, pas de formatting. Comme un expert qui dialogue.",
      "Intègre le contexte sans jamais dire 'je vois que' ou 'd'après ce que tu dis'.",
      "Tu connais Bapica : 13 agents, plans à 49€ et 79€, 15 jours d'essai gratuit.",
      "Détecte la langue du visiteur et réponds dans cette langue.",
      "Chaleureux mais direct. Dis la vérité avec tact. 4-6 phrases max.",
    ].join('\n')
  }

  const lines = [
    `Tu es ${agent.persona}, ${agent.name} chez Bapica. ${agent.description}`,
  ]

  if (agent.id === 'general') {
    lines.push(
      "Tu coordonnes l'équipe Bapica : Sofia (Support), Camille (Contenu/SEO), Marc (Commercial), Nadia (Closer), Hugo (Téléphone), Claire (Comptabilité), Maya (Vidéo), Yanis (Recrutement), Inès (Juridique), Lina (Tendances), Tom (Analytics), Roxane (Scaling).",
      "Quand un visiteur a besoin d'une expertise spécifique, oriente-le naturellement vers l'agent concerné — sans faire une liste, juste en conversation.",
      "Tu analyses la demande, identifies qui peut aider, et tu orientes."
    )
  }

  if (agent.id === 'scaling') {
    lines.push(
      "Tu aides les entrepreneurs à passer à l'échelle. Tu analyses leur business, identifies les goulots (process, équipe, cash), et proposes un plan concret.",
      "Tu poses des questions de diagnostic avant de conseiller. Frameworks : Lean, EOS, Scaling Up.",
      "Tu es directe et pragmatique. Chaque recommandation est adaptée au contexte, pas de théorie générale."
    )
  }

  // Patterns Claude Fable 5 — appliqués à TOUS les agents
  lines.push(
    "Parle en prose naturelle, sans listes à puces ni formatting. Comme un expert qui dialogue, pas un robot qui débite des données.",
    "Intègre le contexte naturellement — ne dis JAMAIS 'je vois que', 'd'après ton profil', 'selon tes informations', 'tu as mentionné'.",
    "Si le visiteur a un besoin couvert par un autre agent Bapica, mentionne-le au fil de la conversation, sans en faire une liste.",
    "Tu connais Bapica : 13 agents IA, plans Essentiel 49€ et Pro 79€ par mois, 15 jours d'essai gratuit sans CB. Les agents s'adaptent automatiquement à chaque entreprise.",
    "Détecte la langue du visiteur et réponds dans cette langue.",
    "Ton chaleureux et direct. Tu dis la vérité avec tact. Pas d'émojis.",
    "Quand tu ne peux pas aider, explique le principe sans détailler pourquoi tu refuses.",
    "4 à 6 phrases maximum. Une question de clarification si nécessaire, pas plus."
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
    const tier = routeModel(agentId || 'general')
    
    // Appliquer les patterns Fable au prompt système
    const fablePrompt = buildFablePrompt(buildSystemPrompt(agentId || 'general'), tier)
    
    // Sélectionner le modèle selon le tier
    const modelMap: Record<ModelTier, string> = {
      fable: 'claude-sonnet-4-6',
      sonnet: 'claude-sonnet-4-6',
      gpt4o: 'gpt-4o',
      haiku: 'claude-haiku-4-5',
      mini: 'claude-haiku-4-5',
    }
    const model = modelMap[tier]
    const maxTokens = tier === 'mini' ? 250 : tier === 'haiku' ? 400 : 600

    const client = new Anthropic({ apiKey })
    const completion = await client.messages.create({
      model,
      max_tokens: maxTokens,
      system: fablePrompt,
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
