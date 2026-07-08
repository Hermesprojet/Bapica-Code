import { NextRequest, NextResponse } from 'next/server'
import Anthropic from '@anthropic-ai/sdk'
import { getAgentById, type AgentConfig } from '@/lib/agents'
import { createClient } from '@supabase/supabase-js'
import { sanitizeUserMessage, isValidAgentId } from '@/lib/security'

// Helpers CORS
function corsHeaders(origin: string | null) {
  const allowed = process.env.NEXT_PUBLIC_SITE_URL
    ? [process.env.NEXT_PUBLIC_SITE_URL, 'https://bapica.com']
    : ['https://bapica.com']
  return {
    'Access-Control-Allow-Origin': allowed.includes(origin ?? '') || !origin ? origin ?? 'https://bapica.com' : 'https://bapica.com',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Max-Age': '86400',
  }
}

export async function OPTIONS(req: NextRequest) {
  return NextResponse.json({}, { headers: corsHeaders(req.headers.get('origin')) })
}

// Route API centrale pour les agents
// POST /api/chat
// Body: { agentId, message, history }

interface HistoryMessage {
  role: 'user' | 'assistant'
  content: string
}

async function verifyAuth(req: NextRequest) {
  const authHeader = req.headers.get('authorization')
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''
  
  if (!supabaseUrl || !supabaseAnonKey) {
    return { error: 'Configuration Supabase manquante', status: 500 }
  }

  const supabase = createClient(supabaseUrl, supabaseAnonKey, {
    auth: { persistSession: false, autoRefreshToken: false }
  })

  // Essayer l'auth via le cookie de session (navigateur)
  const { data: { user }, error } = await supabase.auth.getUser()
  
  if (error || !user) {
    return { error: 'Non authentifié. Connectez-vous pour utiliser cette API.', status: 401 }
  }

  return { user }
}

// Le modèle déclaré dans lib/agents.ts ('claude-sonnet-4') est un alias interne ;
// on le résout vers un identifiant de modèle valide de l'API Claude.
function resolveModel(model: string): string {
  if (model.startsWith('claude-opus')) return 'claude-opus-4-8'
  if (model.startsWith('claude-haiku')) return 'claude-haiku-4-5'
  return 'claude-sonnet-4-6'
}

function buildSystemPrompt(agent: AgentConfig): string {
  return [
    `Tu es « ${agent.persona} », l'agent « ${agent.name} » de la plateforme Bapica.`,
    `Mission : ${agent.description}`,
    agent.tools.length
      ? `Outils/intégrations à ta disposition : ${agent.tools.join(', ')}.`
      : '',
    'Réponds de manière professionnelle, claire et utile pour des PME et indépendants.',
    "Détecte automatiquement la langue de l'utilisateur et réponds dans cette même langue, quelle qu'elle soit.",
    "Si une demande sort de ton domaine, dis-le honnêtement et oriente l'utilisateur vers l'agent adapté.",
    'Adopte un ton professionnel, courtois et sobre.',
    "N'utilise pas d'émojis ni d'icônes.",
    "Réponds en texte simple, sans mise en forme Markdown (pas de #, de **, ni de symboles de liste) : ces caractères s'affichent tels quels et nuisent à la lisibilité. Pour une énumération, écris des phrases courtes ou des tirets simples.",
    'Va à l\'essentiel : des réponses concises et directes, sans préambule superflu.',
  ]
    .filter(Boolean)
    .join('\n')
}

export async function POST(req: NextRequest) {
  try {
    // Vérifier l'authentification
    const auth = await verifyAuth(req)
    if ('error' in auth) {
      return NextResponse.json({ error: auth.error }, { status: auth.status, headers: corsHeaders(req.headers.get('origin')) })
    }

    const { agentId, message, history } = await req.json()

    if (!agentId || !message) {
      return NextResponse.json(
        { error: 'agentId et message requis' },
        { status: 400, headers: corsHeaders(req.headers.get('origin')) }
      )
    }

    // Valider l'agentId (liste blanche)
    if (!isValidAgentId(agentId)) {
      return NextResponse.json({ error: 'Agent invalide' }, { status: 400, headers: corsHeaders(req.headers.get('origin')) })
    }

    // Sanitize le message utilisateur
    const safeMessage = sanitizeUserMessage(message)

    const agent = getAgentById(agentId)
    if (!agent) {
      return NextResponse.json({ error: 'Agent introuvable' }, { status: 404, headers: corsHeaders(req.headers.get('origin')) })
    }

    // TODO: Vérifier l'abonnement de l'utilisateur et le rate limiting

    const response = await callClaude(agent, message, history ?? [])

    return NextResponse.json({ response, agentId }, { headers: corsHeaders(req.headers.get('origin')) })
  } catch (error) {
    console.error('Chat API error:', error)
    if (error instanceof Anthropic.APIError) {
      const status = error.status ?? 500
      const detail =
        status === 401
          ? 'Clé API Claude invalide. Vérifiez votre configuration.'
          : status === 429
          ? 'Limite de requêtes atteinte. Réessayez dans quelques instants.'
          : "Erreur lors de l'appel à l'API Claude."
      return NextResponse.json({ error: detail }, { status })
    }
    return NextResponse.json(
      { error: 'Erreur interne du serveur' },
      { status: 500 }
    )
  }
}

async function callClaude(
  agent: AgentConfig,
  message: string,
  history: HistoryMessage[]
): Promise<string> {
  const apiKey = process.env.ANTHROPIC_API_KEY

  if (!apiKey) {
    return '⚠️ Agent non configuré. Veuillez ajouter une clé API Claude (ANTHROPIC_API_KEY) dans les paramètres.'
  }

  const client = new Anthropic({ apiKey })

  // On ne garde que les tours user/assistant valides, puis on ajoute le message courant.
  const messages: Anthropic.MessageParam[] = [
    ...history
      .filter(
        (m) =>
          (m.role === 'user' || m.role === 'assistant') &&
          typeof m.content === 'string' &&
          m.content.trim().length > 0
      )
      .map((m) => ({ role: m.role, content: m.content })),
    { role: 'user' as const, content: message },
  ]

  const completion = await client.messages.create({
    model: resolveModel(agent.model),
    max_tokens: agent.maxTokens,
    temperature: agent.temperature,
    system: buildSystemPrompt(agent),
    messages,
  })

  return completion.content
    .filter((block): block is Anthropic.TextBlock => block.type === 'text')
    .map((block) => block.text)
    .join('\n')
    .trim()
}
