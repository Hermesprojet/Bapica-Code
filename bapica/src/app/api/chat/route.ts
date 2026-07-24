import { NextRequest, NextResponse } from 'next/server'
import Anthropic from '@anthropic-ai/sdk'
import { getAgentById, type AgentConfig } from '@/lib/agents'
import { createClient } from '@supabase/supabase-js'
import { sanitizeUserMessage, isValidAgentId } from '@/lib/security'
import { buildClientMemory, buildMemoryContext, addToMemory, type ClientMemory, type ConversationSummary } from '@/lib/client-memory'
import { buildBusinessBrief } from '@/lib/business-context'
import { retrieveClientContext } from '@/lib/client-knowledge'
import { twentyTools } from '@/lib/tools/twenty-tools'
import { consultAgentTool, runAgentConsult } from '@/lib/tools/agent-consult'
import { listPlatformsTool, readPlatformTool, proposeActionTool, listClientPlatforms, readFromPlatform } from '@/lib/tools/platform-call'
import { readEmailsTool, proposeEmailTool, runReadEmails } from '@/lib/tools/email-tools'
import { auditSiteTool, auditSite } from '@/lib/tools/seo-audit'
import { proposeRdvTool, rdvSummary, type RdvInput } from '@/lib/tools/calendar-tools'
import { proposeDocumentTool } from '@/lib/tools/document-tools'
import { buildDeliverable, type DeliverableKind } from '@/lib/deliverables'
import { createDeliverable } from '@/lib/deliverables/store'
import { tagInteractionTool } from '@/lib/tools/tag-tools'
import { createTag } from '@/lib/tags/store'
import { scheduleRemindersTool } from '@/lib/tools/reminder-tools'
import { createReminders } from '@/lib/reminders/store'
import { proposeSmsTool } from '@/lib/tools/sms-tools'
import { readBankTool } from '@/lib/tools/bank-tools'
import { readBalances, readTransactions } from '@/lib/bank/gocardless'
import { keywordResearchTool } from '@/lib/tools/keyword-tools'
import { researchKeywords } from '@/lib/seo/keywords'
import { webSearchTool, analyzeCompanyTool, findProspectsTool } from '@/lib/tools/research-tools'
import { webSearch, researchCompany } from '@/lib/company-research'
import { searchLeads } from '@/lib/apollo'
import { domainSearch, cleanDomain } from '@/lib/hunter'
import { searchLocalBusinesses } from '@/lib/apify'
import { proposeAutomationTool } from '@/lib/tools/automation-tools'
import { createAutomation } from '@/lib/automations/store'
import { createAction } from '@/lib/actions/store'
import { searchKnowledge, formatKnowledgeContext } from '@/lib/rag'
import { searchLocalCompetitors, searchJobTrends, getSectorNews } from '@/lib/live-data'
import { getOptimalModel, compressPrompt, getCachedRAG, setCachedRAG, ragCacheKey, memoizeRAG, extractDeliverables } from '@/lib/optimizations'
import { getSystemPromptForAgent } from '@/lib/agent-prompts'

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
  const authHeader = req.headers.get('authorization') || ''
  // Le client envoie « Authorization: Bearer <access_token> » ; on valide ce jeton.
  const token = authHeader.replace(/^Bearer\s+/i, '').trim()
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''

  if (!supabaseUrl || !supabaseAnonKey) {
    return { error: 'Configuration Supabase manquante', status: 500 as const }
  }
  if (!token) {
    return { error: 'Non authentifié. Connectez-vous pour utiliser cette API.', status: 401 as const }
  }

  const supabase = createClient(supabaseUrl, supabaseAnonKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  })

  // Valide le jeton JWT transmis par le navigateur et récupère l'utilisateur.
  const { data: { user }, error } = await supabase.auth.getUser(token)

  if (error || !user) {
    return { error: 'Non authentifié. Connectez-vous pour utiliser cette API.', status: 401 as const }
  }

  return { user }
}

// Le modèle déclaré dans lib/agents.ts ('claude-sonnet-4') est un alias interne ;
// on le résout vers un identifiant de modèle valide de l'API Claude.
function resolveModel(agentModel: string, agentId: string, message?: string): string {
  // Router intelligent si message fourni — on passe le VRAI id d'agent pour que
  // les agents critiques (legal, accounting, prospection) obtiennent Sonnet.
  if (message) {
    const optimal = getOptimalModel(agentId, message)
    return optimal.model
  }
  if (agentModel.startsWith('claude-opus')) return 'claude-opus-4-1'
  if (agentModel.startsWith('claude-haiku')) return 'claude-haiku-4-5'
  return 'claude-sonnet-4-5'
}

function buildSystemPrompt(agent: AgentConfig): string {
  const lines = [
    `Tu es ${agent.persona}, ${agent.name} chez Bapica.`,
    // Rôle, méthode et règles propres à cet agent (lib/agent-prompts.ts)
    getSystemPromptForAgent(agent.id),
    agent.tools.length
      ? `Tes outils : ${agent.tools.join(', ')}.`
      : '',
  ]

  // Patterns Claude Fable 5
  lines.push(
    'Parle en prose naturelle, sans listes à puces ni formatting. Comme un expert qui dialogue avec un dirigeant de PME.',
    'Intègre le contexte sans jamais dire "je vois que", "d\'après ton profil", "selon tes données". Les infos que tu as sur le client sont naturelles, pas des stats à réciter.',
    'Tu connais Bapica : 10 agents IA spécialisés, plans 49€ et 79€, 15 jours d\'essai, dashboard avec score de santé et ROI.',
    "CAPACITÉ CLÉ DE BAPICA — À NE JAMAIS CONTREDIRE : Bapica automatise le CONTACT avec les clients de l'utilisateur et AGIT sur ses outils, ce n'est pas un simple CRM ni un outil d'organisation. Concrètement : Sofia répond aux clients par chat et par email 24h/24 ; Hugo répond aux appels téléphoniques entrants (standard) ; Nadia appelle les prospects par téléphone ; Claire envoie les factures et relance les impayés par email ; Marc envoie les messages de prospection par email et LinkedIn ; Camille crée le contenu ET le PUBLIE / le PROGRAMME sur les réseaux sociaux connectés (LinkedIn, Instagram, Facebook), sur autorisation du client.",
    "Quand on te demande si les agents peuvent contacter/appeler/répondre aux clients (téléphone, email) OU se connecter aux réseaux sociaux et y publier (LinkedIn, Instagram, Facebook) : réponds OUI, clairement, et cite l'agent qui le fait (Sofia, Hugo, Nadia, Claire, Marc, ou Camille pour les réseaux). INTERDIT : ne réponds JAMAIS « je ne peux pas contacter vos clients », « je ne peux pas me connecter à LinkedIn/Instagram/Facebook », « je ne peux pas publier », « je suis une IA de création, pas de publication », « c'est une limite volontaire », ni « je me contente d'organiser vos données » — ces réponses sont fausses et contraires à Bapica. Si la connexion à une plateforme n'est pas encore branchée, explique comment la brancher (Paramètres → connexions) ; ne nie jamais la capacité.",
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
    
    // Le profil business est saisi à l'onboarding et stocké dans user_metadata ;
    // on le lit là en priorité (la table profiles ne le contient pas toujours).
    let onboarding: any = auth.user.user_metadata?.onboarding_data || {}
    let clientMemory: ClientMemory
    try {
      const { data: profile } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', auth.user.id)
        .single()

      if (!onboarding || Object.keys(onboarding).length === 0) {
        onboarding = profile?.onboarding_data || {}
      }
      const history = profile?.conversation_history || []
      clientMemory = buildClientMemory(onboarding, history)
    } catch {
      clientMemory = buildClientMemory(onboarding, [])
    }

    // Injecter le contexte mémoire + le BRIEF business du client dans le prompt,
    // pour que l'agent maîtrise l'entreprise du client et conseille concrètement.
    const businessBrief = buildBusinessBrief(onboarding)
    const memoryContext = [businessBrief, buildMemoryContext(clientMemory)].filter(Boolean).join('\n\n')

    // RAG + Live data — avec cache pour les questions fréquentes
    let ragContext = ''
    const ragKey = ragCacheKey(agent.id, safeMessage)
    const cachedRAG = getCachedRAG(ragKey)

    if (cachedRAG) {
      ragContext = cachedRAG
    } else {
      // Léo (orchestrateur/stratégie) et Camille (SEO/contenu) profitent aussi de la
      // base de connaissances métier — ils en étaient exclus sans raison.
      const ragAgents = ['general', 'prospection-strategie', 'content', 'support', 'recruiter', 'legal', 'accounting']
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
      // Veille marché / actualité sectorielle : rebranché sur Marc (prospection &
      // croissance), l'agent réel le plus pertinent (il n'existe pas d'agent « trends »).
      if (agent.id === 'prospection-strategie' && sector) {
        const mapped = sector.includes('tech') || sector.includes('saas') ? 'tech'
          : sector.includes('retail') || sector.includes('commerce') ? 'retail'
          : sector.includes('finance') || sector.includes('banque') ? 'finance'
          : 'general'
        liveContext += await getSectorNews(mapped)
      }
    } catch { /* Live data silencieux */ }

    // RAG par client : documents de l'entreprise téléversés par l'utilisateur.
    let clientKnowledge = ''
    try {
      const ctx = await retrieveClientContext(auth.user.id, safeMessage)
      if (ctx) clientKnowledge = `\n\n--- Documents de l'entreprise du client (source de vérité) ---\n${ctx}\n---`
    } catch { /* RAG client silencieux */ }

    const response = await callClaude(agent, safeMessage, history ?? [], memoryContext + ragContext + liveContext + clientKnowledge, auth.user.id)

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
  memoryContext: string = '',
  userId?: string
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

  // Outils CRM réservés aux agents commerciaux (pas à l'agent général Léo,
  // sinon il croit que Bapica n'est qu'un CRM).
  const agentForTools = agent
  const isCommercial = agentForTools?.id === 'prospection-strategie' || agentForTools?.id === 'closer'
  const crmTools = isCommercial
    ? [...(twentyTools as unknown as any[]), findProspectsTool as unknown as any]
    : []

  // Collaboration inter-agents + lecture des plateformes connectées par le client.
  // Disponibles pour TOUS les agents (les outils plateformes sont en LECTURE SEULE).
  const tools = [
    ...crmTools,
    consultAgentTool as unknown as any,
    ...(userId
      ? [
          listPlatformsTool as unknown as any,
          readPlatformTool as unknown as any,
          proposeActionTool as unknown as any,
          readEmailsTool as unknown as any,
          proposeEmailTool as unknown as any,
          auditSiteTool as unknown as any,
          proposeRdvTool as unknown as any,
          proposeDocumentTool as unknown as any,
          tagInteractionTool as unknown as any,
          scheduleRemindersTool as unknown as any,
          proposeSmsTool as unknown as any,
          readBankTool as unknown as any,
          keywordResearchTool as unknown as any,
          webSearchTool as unknown as any,
          analyzeCompanyTool as unknown as any,
          proposeAutomationTool as unknown as any,
        ]
      : []),
  ]

    // ── Prompt caching ────────────────────────────────────────────────────────
    // Le cache est un match de PRÉFIXE (ordre de rendu : tools → system → messages).
    // On découpe donc le prompt système en deux blocs : le premier est STABLE pour un
    // agent donné (persona, rôle, règles — aucune donnée client, aucun horodatage) et
    // porte le cache_control ; le second contient le contexte client, volatil, et reste
    // volontairement APRÈS le point de cache.
    // Les deux appels réutilisent CE MÊME tableau : auparavant la boucle d'outils
    // renvoyait un prompt différent (l'un compressé, l'autre non), donc chaque tour
    // repayait le prompt entier au prix fort.
    const systemBlocks: Anthropic.TextBlockParam[] = [
      {
        type: 'text',
        text: compressPrompt(buildSystemPrompt(agent), agent.id),
        cache_control: { type: 'ephemeral' },
      },
      ...(memoryContext
        ? [{ type: 'text' as const, text: '\n\n--- Contexte client ---\n' + memoryContext }]
        : []),
    ]

    const completion = await client.messages.create({
      model: resolveModel(agent.model, agent.id, message),
      max_tokens: agent.maxTokens,
      temperature: agent.temperature,
      system: systemBlocks,
      tools,
      messages,
    })

    // Vérification du cache (logs Vercel). Attendu : « write » élevé au 1er message
    // d'une conversation, puis « read » élevé aux suivants. Si « read » reste à 0
    // d'un message à l'autre, c'est qu'un élément du préfixe varie (voir plus haut).
    console.log(
      `[cache] ${agent.id} write=${completion.usage.cache_creation_input_tokens ?? 0}`
      + ` read=${completion.usage.cache_read_input_tokens ?? 0}`
      + ` uncached=${completion.usage.input_tokens}`
    )

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
          if (tool.name === 'auditer_site') {
            const i = tool.input as { url?: string }
            const r = await auditSite(String(i?.url || ''))
            result = JSON.stringify(r.ok ? { ok: true, audit: r.audit } : { ok: false, erreur: r.error })
          } else if (tool.name === 'lire_emails' && userId) {
            const i = tool.input as { limit?: number }
            const r = await runReadEmails(userId, Number(i?.limit) || 10)
            result = JSON.stringify(r.ok ? { ok: true, emails: r.emails } : { ok: false, erreur: r.error })
          } else if (tool.name === 'proposer_email' && userId) {
            const i = tool.input as { to?: string; subject?: string; text?: string }
            try {
              const actionId = await createAction({
                userId,
                agentId: agent.id,
                provider: 'email',
                method: 'SEND',
                path: '',
                body: { to: String(i?.to || ''), subject: String(i?.subject || ''), text: String(i?.text || '') },
                summary: `Envoyer un email à ${i?.to || '?'} — objet : ${i?.subject || '(sans objet)'}`,
              })
              result = JSON.stringify({ ok: true, action_id: actionId, statut: "en attente de validation par l'utilisateur" })
            } catch (err) {
              const m = String(err instanceof Error ? err.message : err)
              result = JSON.stringify({ ok: false, erreur: m.includes('ACTIONS_TABLE_MISSING') ? 'Base non initialisée : exécutez supabase-schema.sql.' : m })
            }
          } else if (tool.name === 'lister_plateformes' && userId) {
            const platforms = await listClientPlatforms(userId)
            result = JSON.stringify({ plateformes: platforms })
          } else if (tool.name === 'lire_plateforme' && userId) {
            const input = tool.input as { provider?: string; path?: string }
            const r = await readFromPlatform(userId, String(input?.provider || ''), String(input?.path || '/'))
            result = JSON.stringify(r.ok ? { ok: true, donnees: r.data } : { ok: false, erreur: r.error })
          } else if (tool.name === 'proposer_action' && userId) {
            // L'agent PROPOSE : rien n'est exécuté ici, l'utilisateur validera.
            const i = tool.input as { provider?: string; method?: string; path?: string; body?: unknown; summary?: string }
            try {
              const actionId = await createAction({
                userId,
                agentId: agent.id,
                provider: String(i?.provider || ''),
                method: String(i?.method || 'POST'),
                path: String(i?.path || '/'),
                body: i?.body,
                summary: String(i?.summary || 'Action sans description'),
              })
              result = JSON.stringify({
                ok: true,
                action_id: actionId,
                statut: "en attente de validation par l'utilisateur",
              })
            } catch (err) {
              const m = String(err instanceof Error ? err.message : err)
              result = JSON.stringify({
                ok: false,
                erreur: m.includes('ACTIONS_TABLE_MISSING')
                  ? 'Base non initialisée : exécutez supabase-schema.sql.'
                  : m,
              })
            }
          } else if (tool.name === 'proposer_rdv' && userId) {
            const i = tool.input as RdvInput
            try {
              const actionId = await createAction({
                userId,
                agentId: agent.id,
                provider: 'calendar',
                method: 'CREATE',
                path: '',
                body: {
                  title: String(i?.title || 'Rendez-vous'),
                  date: String(i?.date || ''),
                  time: String(i?.time || ''),
                  duration_minutes: Number(i?.duration_minutes) || 30,
                  attendee: i?.attendee ? String(i.attendee) : '',
                  location: i?.location ? String(i.location) : '',
                  description: i?.description ? String(i.description) : '',
                },
                summary: rdvSummary(i),
              })
              result = JSON.stringify({ ok: true, action_id: actionId, statut: "en attente de validation par l'utilisateur" })
            } catch (err) {
              const m = String(err instanceof Error ? err.message : err)
              result = JSON.stringify({ ok: false, erreur: m.includes('ACTIONS_TABLE_MISSING') ? 'Base non initialisée : exécutez supabase-schema.sql.' : m })
            }
          } else if (tool.name === 'proposer_document' && userId) {
            const i = tool.input as { kind?: string; title?: string; content?: string; columns?: unknown; rows?: unknown }
            try {
              const kind = (['pdf', 'excel', 'csv', 'markdown', 'text'].includes(String(i?.kind)) ? i!.kind : 'pdf') as DeliverableKind
              const file = buildDeliverable({
                kind,
                title: String(i?.title || 'Document'),
                content: i?.content != null ? String(i.content) : undefined,
                columns: Array.isArray(i?.columns) ? (i!.columns as unknown[]).map(String) : undefined,
                rows: Array.isArray(i?.rows) ? (i!.rows as unknown[]).map((r) => (Array.isArray(r) ? (r as unknown[]).map((c) => (typeof c === 'number' ? c : String(c))) : [String(r)])) : undefined,
              })
              const docId = await createDeliverable({
                userId, agentId: agent.id, kind, title: String(i?.title || 'Document'),
                filename: file.filename, mime: file.mime, content: file.content,
              })
              result = JSON.stringify({ ok: true, document_id: docId, filename: file.filename, statut: 'disponible dans « Documents »' })
            } catch (err) {
              const m = String(err instanceof Error ? err.message : err)
              result = JSON.stringify({ ok: false, erreur: m.includes('DELIVERABLES_TABLE_MISSING') ? 'Base non initialisée : exécutez supabase-schema.sql.' : m })
            }
          } else if (tool.name === 'etiqueter_echange' && userId) {
            const i = tool.input as { tag?: string; contact?: string; channel?: string; note?: string }
            try {
              const tagId = await createTag({
                userId, agentId: agent.id,
                tag: String(i?.tag || 'autre'),
                contact: i?.contact ? String(i.contact) : undefined,
                channel: i?.channel ? String(i.channel) : undefined,
                note: i?.note ? String(i.note) : undefined,
              })
              result = JSON.stringify({ ok: true, tag_id: tagId, statut: 'étiquette enregistrée' })
            } catch (err) {
              const m = String(err instanceof Error ? err.message : err)
              result = JSON.stringify({ ok: false, erreur: m.includes('TAGS_TABLE_MISSING') ? 'Base non initialisée : exécutez supabase-schema.sql.' : m })
            }
          } else if (tool.name === 'programmer_relances' && userId) {
            const i = tool.input as { client?: string; contact_email?: string; invoice_ref?: string; amount?: number; currency?: string; relances?: unknown }
            try {
              const steps = Array.isArray(i?.relances)
                ? (i!.relances as any[]).map((s) => ({
                    offsetDays: Number(s?.offset_days) || 0,
                    stage: s?.stage ? String(s.stage) : undefined,
                    subject: s?.subject ? String(s.subject) : undefined,
                    body: s?.body ? String(s.body) : undefined,
                  }))
                : []
              if (steps.length === 0) {
                result = JSON.stringify({ ok: false, erreur: 'Fournis au moins une étape de relance.' })
              } else {
                const n = await createReminders({
                  userId, client: String(i?.client || 'Client'),
                  contactEmail: i?.contact_email ? String(i.contact_email) : undefined,
                  invoiceRef: i?.invoice_ref ? String(i.invoice_ref) : undefined,
                  amount: typeof i?.amount === 'number' ? i.amount : undefined,
                  currency: i?.currency ? String(i.currency) : undefined,
                  steps,
                })
                result = JSON.stringify({ ok: true, relances_programmees: n, statut: 'visibles dans « Relances »' })
              }
            } catch (err) {
              const m = String(err instanceof Error ? err.message : err)
              result = JSON.stringify({ ok: false, erreur: m.includes('REMINDERS_TABLE_MISSING') ? 'Base non initialisée : exécutez supabase-schema.sql.' : m })
            }
          } else if (tool.name === 'proposer_automation' && userId) {
            const i = tool.input as { title?: string; description?: string; cron?: string; schedule_label?: string; agent_id?: string }
            try {
              const autoId = await createAutomation({
                userId,
                agentId: i?.agent_id ? String(i.agent_id) : agent.id,
                title: String(i?.title || 'Automatisation'),
                description: String(i?.description || ''),
                cron: String(i?.cron || '0 8 * * 1'),
                scheduleLabel: i?.schedule_label ? String(i.schedule_label) : undefined,
              })
              result = JSON.stringify({ ok: true, automation_id: autoId, statut: "en attente de validation du client (page « Automatisations »)" })
            } catch (err) {
              const m = String(err instanceof Error ? err.message : err)
              result = JSON.stringify({ ok: false, erreur: m.includes('AUTOMATIONS_TABLE_MISSING') ? 'Base non initialisée : exécutez supabase-schema.sql.' : m })
            }
          } else if (tool.name === 'rechercher_web') {
            const i = tool.input as { query?: string }
            try {
              const results = await webSearch(String(i?.query || ''))
              result = JSON.stringify(results.length ? { ok: true, resultats: results.slice(0, 8) } : { ok: false, erreur: "Aucun résultat (SERPAPI_KEY absente ou pas de résultat)." })
            } catch (err) {
              result = JSON.stringify({ ok: false, erreur: String(err instanceof Error ? err.message : err) })
            }
          } else if (tool.name === 'analyser_entreprise') {
            const i = tool.input as { companyName?: string; website?: string; sector?: string; city?: string }
            try {
              const r = await researchCompany({
                companyName: String(i?.companyName || ''),
                website: i?.website ? String(i.website) : undefined,
                sector: i?.sector ? String(i.sector) : undefined,
                city: i?.city ? String(i.city) : undefined,
              })
              result = JSON.stringify({ ok: true, profil: r.summary, sources: r.sources })
            } catch (err) {
              result = JSON.stringify({ ok: false, erreur: String(err instanceof Error ? err.message : err) })
            }
          } else if (tool.name === 'trouver_prospects') {
            const i = tool.input as { sector?: string; city?: string; titles?: string[]; locations?: string[]; keywords?: string; domain?: string }
            try {
              if (i?.sector && i?.city) {
                const r = await searchLocalBusinesses({ sector: String(i.sector), city: String(i.city) })
                result = JSON.stringify({ ok: true, source: 'google-maps', total: r.total, prospects: r.leads.slice(0, 20) })
              } else if (i?.domain) {
                const r = await domainSearch(cleanDomain(String(i.domain)))
                result = JSON.stringify({ ok: true, source: 'hunter', total: r.total, prospects: r.leads.slice(0, 15) })
              } else {
                const r = await searchLeads({
                  titles: Array.isArray(i?.titles) ? i!.titles.map(String) : undefined,
                  locations: Array.isArray(i?.locations) ? i!.locations.map(String) : undefined,
                  keywords: i?.keywords ? String(i.keywords) : undefined,
                })
                result = JSON.stringify({ ok: true, source: 'apollo', total: r.total, prospects: r.leads.slice(0, 15) })
              }
            } catch (err) {
              const m = String(err instanceof Error ? err.message : err)
              const clean = /APOLLO_NOT_CONFIGURED|HUNTER_NOT_CONFIGURED|APIFY_NOT_CONFIGURED/.test(m)
                ? "Recherche de prospects non configurée (clé Apollo, Hunter ou Apify manquante) — voir Prospects / Connexions."
                : m
              result = JSON.stringify({ ok: false, erreur: clean })
            }
          } else if (tool.name === 'rechercher_motscles') {
            const i = tool.input as { seed?: string; lang?: string }
            const r = await researchKeywords(String(i?.seed || ''), String(i?.lang || 'fr'))
            result = JSON.stringify(r.ok ? { ok: true, seed: r.seed, mots_cles: r.keywords, questions: r.questions } : { ok: false, erreur: r.error })
          } else if (tool.name === 'lire_banque' && userId) {
            const i = tool.input as { action?: string }
            const r = i?.action === 'transactions' ? await readTransactions(userId) : await readBalances(userId)
            if (r.ok) {
              result = JSON.stringify(i?.action === 'transactions' ? { ok: true, transactions: (r as any).transactions } : { ok: true, soldes: (r as any).balances })
            } else {
              const notConnected = r.error === 'not-connected' || r.error === 'no-credentials'
              result = JSON.stringify({ ok: false, erreur: notConnected ? 'Aucune banque connectée (Connexions → Banque).' : r.error })
            }
          } else if (tool.name === 'proposer_sms' && userId) {
            const i = tool.input as { to?: string; text?: string }
            try {
              const actionId = await createAction({
                userId, agentId: agent.id, provider: 'sms', method: 'SEND', path: '',
                body: { to: String(i?.to || ''), text: String(i?.text || '') },
                summary: `Envoyer un SMS à ${i?.to || '?'}`,
              })
              result = JSON.stringify({ ok: true, action_id: actionId, statut: "en attente de validation par l'utilisateur" })
            } catch (err) {
              const m = String(err instanceof Error ? err.message : err)
              result = JSON.stringify({ ok: false, erreur: m.includes('ACTIONS_TABLE_MISSING') ? 'Base non initialisée : exécutez supabase-schema.sql.' : m })
            }
          } else if (tool.name === 'consulter_agent') {
            // Collaboration inter-agents réelle : le confrère répond avec le même contexte client.
            const input = tool.input as { agent_id?: string; question?: string }
            const answer = await runAgentConsult(
              client,
              String(input?.agent_id || 'general'),
              String(input?.question || ''),
              memoryContext
            )
            result = JSON.stringify({ agent: input?.agent_id, reponse: answer })
          } else {
            // Les credentials CRM doivent être fournis par l'utilisateur connecté
            result = JSON.stringify({ message: `Outil ${tool.name} appelé avec ${JSON.stringify(tool.input)}. Configuration CRM requise.` })
          }
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
        model: resolveModel(agent.model, agent.id, message),
        max_tokens: agent.maxTokens,
        temperature: agent.temperature,
        system: systemBlocks,
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
