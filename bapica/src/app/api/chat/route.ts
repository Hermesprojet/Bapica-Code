import { NextRequest, NextResponse } from 'next/server'
import Anthropic from '@anthropic-ai/sdk'
import { getAgentById, type AgentConfig } from '@/lib/agents'
import { createClient } from '@supabase/supabase-js'
import { sanitizeUserMessage, isValidAgentId } from '@/lib/security'
import { buildClientMemory, buildMemoryContext, addToMemory, type ClientMemory, type ConversationSummary } from '@/lib/client-memory'
import { twentyTools } from '@/lib/tools/twenty-tools'
import { searchKnowledge, formatKnowledgeContext } from '@/lib/rag'
import { searchLocalCompetitors, searchJobTrends, getSectorNews } from '@/lib/live-data'
import { getOptimalModel, compressPrompt, getCachedRAG, setCachedRAG, ragCacheKey, memoizeRAG, extractDeliverables } from '@/lib/optimizations'

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
function resolveModel(agentModel: string, message?: string): string {
  // Router intelligent si message fourni
  if (message) {
    const optimal = getOptimalModel(agentModel === 'claude-sonnet-4' ? 'analytics' : 'general', message)
    return optimal.model
  }
  if (agentModel.startsWith('claude-opus')) return 'claude-opus-4-1'
  if (agentModel.startsWith('claude-haiku')) return 'claude-haiku-4-5'
  return 'claude-sonnet-4-5'
}

function buildSystemPrompt(agent: AgentConfig): string {
  const lines = [
    `Tu es ${agent.persona}, ${agent.name} chez Bapica. ${agent.description}`,
    agent.tools.length
      ? `Tes outils : ${agent.tools.join(', ')}.`
      : '',
  ]

  // Patterns Claude Fable 5
  lines.push(
    'Parle en prose naturelle, sans listes à puces ni formatting. Comme un expert qui dialogue avec un dirigeant de PME.',
    'Intègre le contexte sans jamais dire "je vois que", "d\'après ton profil", "selon tes données". Les infos que tu as sur le client sont naturelles, pas des stats à réciter.',
    'Tu connais Bapica : 13 agents, plans 49€ et 79€, 15 jours d\'essai, dashboard avec score de santé et ROI.',
    'Adapte ton niveau de détail à la maturité du client : simple pour un débutant, technique pour un expert.',
    'Pour les questions juridiques ou financières : donne l\'information factuelle, pas une recommandation. Tu n\'es pas avocat ni conseiller financier.',
    'Quand tu ne peux pas aider, explique le principe sans détailler le refus. Oriente vers l\'agent ou la ressource adaptée.',
    'Ne crée pas de dépendance : si quelqu\'un te traite comme son seul soutien, rappelle gentiment que Bapica est un outil, pas un substitut aux relations humaines.',
    'Détecte la langue et réponds dans cette langue. Ton chaleureux et direct. Pas d\'émojis.',
    'Réponses concises : 4 à 8 phrases, sans préambule.',
  )

  return lines.filter(Boolean).join('\n')
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
        { error: 'agent.id et message requis' },
        { status: 400, headers: corsHeaders(req.headers.get('origin')) }
      )
    }

    // Valider l'agent.id (liste blanche)
    if (!isValidAgentId(agentId)) {
      return NextResponse.json({ error: 'Agent invalide' }, { status: 400, headers: corsHeaders(req.headers.get('origin')) })
    }

    // Sanitize le message utilisateur
    const safeMessage = sanitizeUserMessage(message)

    const agent = getAgentById(agentId)
    if (!agent) {
      return NextResponse.json({ error: 'Agent introuvable' }, { status: 404, headers: corsHeaders(req.headers.get('origin')) })
    }

    // Charger ou créer la mémoire client
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
    const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''
    const supabase = createClient(supabaseUrl, supabaseAnonKey)
    
    let clientMemory: ClientMemory
    try {
      const { data: profile } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', auth.user.id)
        .single()
      
      const onboarding = profile?.onboarding_data || {}
      const history = profile?.conversation_history || []
      clientMemory = buildClientMemory(onboarding, history)
    } catch {
      clientMemory = buildClientMemory({}, [])
    }

    // Injecter le contexte mémoire dans le system prompt
    const memoryContext = buildMemoryContext(clientMemory)

    // RAG + Live data — avec cache pour les questions fréquentes
    let ragContext = ''
    const ragKey = ragCacheKey(agent.id, safeMessage)
    const cachedRAG = getCachedRAG(ragKey)

    if (cachedRAG) {
      ragContext = cachedRAG
    } else {
      const ragAgents = ['prospection-strategie', 'support', 'recruiter', 'legal', 'accounting', 'analytics', 'trends']
      if (ragAgents.includes(agent.id)) {
        try {
          const matches = await searchKnowledge(safeMessage, auth.user.id, agent.id)
          ragContext = formatKnowledgeContext(matches)
          if (ragContext) setCachedRAG(ragKey, ragContext)
        } catch { /* RAG silencieux */ }
      }
    }

    // Live data — concurrence locale, offres d'emploi, actualités secteur
    let liveContext = ''
    try {
      const sector = auth.user.user_metadata?.sector || auth.user.user_metadata?.activity || ''
      const location = auth.user.user_metadata?.location || ''
      
      if (agent.id === 'prospection-strategie' && sector && location) {
        liveContext += await searchLocalCompetitors(sector, location)
      }
      if (agent.id === 'recruiter' && location) {
        liveContext += await searchJobTrends(sector || 'commercial', location)
      }
      if (agent.id === 'trends' && sector) {
        const mapped = sector.includes('tech') || sector.includes('saas') ? 'tech' 
          : sector.includes('retail') || sector.includes('commerce') ? 'retail'
          : sector.includes('finance') || sector.includes('banque') ? 'finance'
          : 'general'
        liveContext += await getSectorNews(mapped)
      }
    } catch { /* Live data silencieux */ }

    const response = await callClaude(agent, safeMessage, history ?? [], memoryContext + ragContext + liveContext)

    // Sauvegarder la conversation dans la mémoire
    const summary: ConversationSummary = {
      timestamp: new Date().toISOString(),
      agentId: agent.id,
      topic: safeMessage.slice(0, 80),
      outcome: response.slice(0, 80),
      keyPoints: [],
    }
    clientMemory = addToMemory(clientMemory, summary)
    
    // Persister dans Supabase
    try {
      await supabase
        .from('profiles')
        .update({ conversation_history: clientMemory.conversationHistory })
        .eq('id', auth.user.id)
    } catch (e) {
      console.error('Memory save failed:', e)
    }

    return NextResponse.json({ response, agentId: agent.id }, { headers: corsHeaders(req.headers.get('origin')) })
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
  history: HistoryMessage[],
  memoryContext: string = ''
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

  // Ajouter les tools CRM si l'agent a accès
  const agentForTools = agent
  const tools = (agentForTools?.id === 'prospection-strategie' || agentForTools?.id === 'closer' || agentForTools?.id === 'general')
    ? twentyTools as unknown as any[]
    : undefined

    const completion = await client.messages.create({
      model: resolveModel(agent.model, message),
      max_tokens: agent.maxTokens,
      temperature: agent.temperature,
      system: compressPrompt(buildSystemPrompt(agent), agent.id) + (memoryContext ? '\n\n--- Contexte client ---\n' + memoryContext : ''),
      tools,
      messages,
    })

    // Boucle tool_use → tool_result (CRM integration)
    let response = completion
    const maxToolRounds = 3
    for (let round = 0; round < maxToolRounds; round++) {
      const toolUses = response.content.filter((b): b is Anthropic.ToolUseBlock => b.type === 'tool_use')
      if (toolUses.length === 0) break

      const toolResults: Anthropic.ToolResultBlockParam[] = []
      for (const tool of toolUses) {
        let result = ''
        try {
          // Les credentials CRM doivent être fournis par l'utilisateur connecté
          // Pour l'instant, on retourne un message informatif
          result = JSON.stringify({ message: `Outil ${tool.name} appelé avec ${JSON.stringify(tool.input)}. Configuration CRM requise.` })
        } catch (e) {
          result = JSON.stringify({ error: 'Échec outil' })
        }
        toolResults.push({ type: 'tool_result', tool_use_id: tool.id, content: result })
      }

      const allMessages = [...messages, 
        { role: 'assistant' as const, content: response.content },
        { role: 'user' as const, content: toolResults }
      ]

      response = await client.messages.create({
        model: resolveModel(agent.model, message),
        max_tokens: agent.maxTokens,
        temperature: agent.temperature,
        system: buildSystemPrompt(agent) + (memoryContext ? '\n\n--- Contexte client ---\n' + memoryContext : ''),
        tools,
        messages: allMessages as any,
      })
    }

    return response.content
      .filter((block): block is Anthropic.TextBlock => block.type === 'text')
      .map((block) => block.text)
      .join('\n')
    .trim()
}
