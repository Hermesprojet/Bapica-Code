import { NextRequest, NextResponse } from 'next/server'
import Anthropic from '@anthropic-ai/sdk'
import AGENTS, { getAgentById } from '@/lib/agents'
import { getSystemPromptForAgent } from '@/lib/agent-prompts'

function corsHeaders(origin: string | null) {
  const allowed = ['https://bapica.com', 'https://bapica-code.vercel.app', 'http://localhost:3000']
  const o = allowed.includes(origin || '') ? origin : ''
  return {
    'Access-Control-Allow-Origin': o || 'https://bapica.com',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  }
}

export async function OPTIONS(req: NextRequest) {
  return NextResponse.json({}, { headers: corsHeaders(req.headers.get('origin')) })
}

interface ChatMessage { role: 'user' | 'assistant'; content: string }

export async function POST(req: NextRequest) {
  try {
    const { agentId, message, history } = await req.json()
    if (!message?.trim()) {
      return NextResponse.json({ error: 'Message requis' }, { status: 400 })
    }

    const agent = getAgentById(agentId || 'general')
    const systemPrompt = buildSystemPrompt(agentId || 'general')

    const apiKey = process.env.ANTHROPIC_API_KEY
    if (!apiKey) {
      return NextResponse.json({ error: 'Service momentanément indisponible (clé API).' }, { status: 503 })
    }

    const client = new Anthropic({ apiKey, timeout: 15000 })
    const completion = await client.messages.create({
      model: 'claude-haiku-4-5',
      max_tokens: 300,
      system: systemPrompt.slice(0, 4000),
      messages: [
        ...(Array.isArray(history) ? history : []).slice(-5),
        { role: 'user' as const, content: message.slice(0, 500) },
      ],
    })

    const text = completion.content
      .filter((b: any) => b.type === 'text')
      .map((b: any) => b.text)
      .join('\n')
      .trim()

    return NextResponse.json({
      response: text,
      agent: agent?.persona || 'Léo',
    }, { headers: corsHeaders(req.headers.get('origin')) })
  } catch (error) {
    console.error('Demo chat error:', String(error))
    return NextResponse.json({ error: 'Service momentanément indisponible.' }, { status: 500, headers: corsHeaders(req.headers.get('origin')) })
  }
}

const BAPICA_CAPS =
  "Bapica, c'est 13 agents IA pour PME qui AUTOMATISENT le contact client et AGISSENT sur les outils (ce n'est pas un simple CRM). Sofia répond aux clients par chat et email 24h/24, Hugo répond aux appels téléphoniques entrants, Nadia appelle les prospects, Claire envoie factures et relances par email, Marc envoie la prospection par email et LinkedIn, Camille crée le contenu ET le publie/programme sur les réseaux sociaux connectés (LinkedIn, Instagram, Facebook), sur autorisation. Quand on demande si les agents peuvent contacter les clients (téléphone/email) ou se connecter aux réseaux sociaux et y publier : réponds OUI et cite l'agent concerné. INTERDIT : ne dis JAMAIS « je ne peux pas contacter vos clients », « je ne peux pas me connecter à LinkedIn/Instagram/Facebook », « je ne peux pas publier », « je suis une IA de création, pas de publication », ni « c'est une limite volontaire ». Si une connexion n'est pas encore branchée, explique comment la faire (Paramètres → connexions), sans nier la capacité."

function buildSystemPrompt(agentId: string): string {
  const agent = getAgentById(agentId)
  if (!agent) {
    return `Tu es Léo, assistant général de Bapica (plans 49-79€, 15 jours d'essai). ${BAPICA_CAPS} Sois utile, concret, en français. 4-6 phrases max.`
  }

  // Rôle, méthode et règles propres à l'agent (lib/agent-prompts.ts)
  let prompt = `Tu es ${agent.persona}, ${agent.name} chez Bapica.\n${getSystemPromptForAgent(agent.id)}\n${BAPICA_CAPS} `

  prompt += ` Sois concret et actionnable. 4-6 phrases. Réponds dans la langue du visiteur.`
  return prompt
}
