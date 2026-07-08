/**
 * Système de Mémoire Conversationnelle Bapica
 * 
 * Inspiré du Memory System de Claude Fable 5 :
 * - Les agents se souviennent des interactions passées avec chaque client
 * - La mémoire est appliquée naturellement, sans jamais dire "je me souviens"
 * - Les souvenirs sensibles ne sont JAMAIS évoqués sans que le client les mentionne
 * - La mémoire s'enrichit progressivement au fil des conversations
 */

export interface ClientMemory {
  // Profil business (issu de l'onboarding)
  businessProfile?: {
    sector?: string
    companyName?: string
    companySize?: string
    employeeCount?: number
    stage?: string
    priorities?: string[]
    painPoints?: string[]
  }
  
  // Historique des interactions
  conversationHistory: ConversationSummary[]
  
  // Préférences apprises
  communicationPreferences?: {
    preferredLanguage?: string
    tone?: 'formal' | 'casual' | 'direct'
    detailLevel?: 'concise' | 'detailed' | 'technical'
  }
  
  // Contexte récent
  recentContext?: {
    lastTopic?: string
    lastAgentUsed?: string
    pendingActions?: string[]
    mood?: 'satisfied' | 'concerned' | 'urgent' | 'exploring'
  }
  
  // Métriques d'usage
  usageMetrics?: {
    firstInteraction?: string
    lastInteraction?: string
    totalConversations?: number
    preferredAgents?: string[]
  }
}

export interface ConversationSummary {
  timestamp: string
  agentId: string
  topic: string
  outcome: string
  keyPoints: string[]
  followUpNeeded?: boolean
}

/**
 * Génère une mémoire client à partir de l'onboarding et de l'historique
 */
export function buildClientMemory(
  onboarding: any,
  history: ConversationSummary[] = []
): ClientMemory {
  return {
    businessProfile: {
      sector: onboarding?.activity,
      companyName: onboarding?.companyName,
      companySize: onboarding?.companySize || 'TPE',
      employeeCount: onboarding?.employeeCount || 1,
      stage: onboarding?.stage || 'early',
      priorities: onboarding?.objectives || [],
      painPoints: onboarding?.adminTasks || [],
    },
    conversationHistory: history.slice(-10), // Garder les 10 dernières
    communicationPreferences: detectPreferences(history),
    recentContext: buildRecentContext(history),
    usageMetrics: buildUsageMetrics(history),
  }
}

/**
 * Détecte les préférences de communication du client
 * (inspiré du Preferences System de Claude Fable)
 */
function detectPreferences(history: ConversationSummary[]): ClientMemory['communicationPreferences'] {
  if (history.length === 0) return undefined
  
  const languages = history.map(h => detectLanguageFromTopic(h.topic))
  const preferredLang = mostFrequent(languages)
  
  return {
    preferredLanguage: preferredLang || 'fr',
    tone: 'direct', // Default Bapica tone
    detailLevel: history.length > 5 ? 'detailed' : 'concise',
  }
}

function detectLanguageFromTopic(text: string): string {
  // Détection simplifiée — l'API Claude gère la vraie détection
  if (/[éèêëàâîïôûùçœ]/.test(text)) return 'fr'
  if (/[áéíóúñ¿¡]/.test(text)) return 'es'
  return 'fr'
}

function mostFrequent(arr: string[]): string | undefined {
  if (arr.length === 0) return undefined
  const counts: Record<string, number> = {}
  arr.forEach(a => { counts[a] = (counts[a] || 0) + 1 })
  return Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0]
}

function buildRecentContext(history: ConversationSummary[]): ClientMemory['recentContext'] {
  if (history.length === 0) return undefined
  
  const last = history[history.length - 1]
  const pendingTopics = history.filter(h => h.followUpNeeded).map(h => h.topic)
  
  return {
    lastTopic: last.topic,
    lastAgentUsed: last.agentId,
    pendingActions: pendingTopics.length > 0 ? pendingTopics : undefined,
    mood: detectMood(history),
  }
}

function detectMood(history: ConversationSummary[]): 'satisfied' | 'concerned' | 'urgent' | 'exploring' {
  if (history.length === 0) return 'exploring'
  
  const recent = history.slice(-3)
  const hasUrgent = recent.some(h => h.topic.toLowerCase().includes('urgent'))
  const hasProblem = recent.some(h => h.outcome.includes('problème'))
  
  if (hasUrgent) return 'urgent'
  if (hasProblem) return 'concerned'
  return 'satisfied'
}

function buildUsageMetrics(history: ConversationSummary[]): ClientMemory['usageMetrics'] {
  if (history.length === 0) return undefined
  
  const agentCounts: Record<string, number> = {}
  history.forEach(h => {
    agentCounts[h.agentId] = (agentCounts[h.agentId] || 0) + 1
  })
  
  const preferred = Object.entries(agentCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([id]) => id)
  
  return {
    firstInteraction: history[0].timestamp,
    lastInteraction: history[history.length - 1].timestamp,
    totalConversations: history.length,
    preferredAgents: preferred,
  }
}

/**
 * Génère le contexte mémoire à injecter dans le prompt système
 * 
 * RÈGLE CRITIQUE (Claude Fable pattern) :
 * - Ne JAMAIS mentionner la mémoire elle-même
 * - Intégrer naturellement : "vous travaillez dans l'immobilier" pas "je vois que vous êtes dans l'immobilier"
 * - Ne JAMAIS évoquer des sujets sensibles que le client n'a pas mentionnés dans cette conversation
 */
export function buildMemoryContext(memory: ClientMemory): string {
  const parts: string[] = []
  const bp = memory.businessProfile
  
  // Contexte business (toujours pertinent)
  if (bp?.sector) {
    parts.push(`Ce client travaille dans le secteur ${bp.sector}.`)
  }
  if (bp?.companyName && bp?.companyName !== 'Votre entreprise') {
    parts.push(`Son entreprise s'appelle ${bp.companyName}, une ${bp.companySize || 'TPE'} de ${bp.employeeCount || 1} personne(s).`)
  }
  if (bp?.priorities?.length) {
    parts.push(`Ses priorités : ${bp.priorities.join(', ')}.`)
  }
  
  // Historique récent (seulement si pertinent pour la conversation)
  if (memory.conversationHistory.length > 0) {
    const lastConv = memory.conversationHistory[memory.conversationHistory.length - 1]
    parts.push(`Dernière conversation il y a peu : ${lastConv.topic}.`)
  }
  
  // Préférences de communication
  if (memory.communicationPreferences?.preferredLanguage) {
    parts.push(`Langue préférée : ${memory.communicationPreferences.preferredLanguage}.`)
  }
  
  // Contexte récent (NEVER sensitive content)
  if (memory.recentContext?.pendingActions?.length) {
    parts.push(`Actions en attente : ${memory.recentContext.pendingActions.join(', ')}.`)
  }
  
  // RAPPEL DES RÈGLES DE MÉMOIRE
  parts.push('')
  parts.push('RÈGLES DE MÉMOIRE :')
  parts.push('- Intègre ces informations naturellement, sans JAMAIS dire "je vois que", "d\'après ton profil", "tu m\'as dit".')
  parts.push('- Ne fais JAMAIS référence au fait que tu as une "mémoire" ou des "données" sur le client.')
  parts.push('- Si le client ne mentionne pas un sujet sensible, ne l\'évoque pas même si tu le sais.')
  parts.push('- Adapte ton ton à l\'humeur détectée du client.')
  
  return parts.join('\n')
}

/**
 * Ajoute un résumé de conversation à la mémoire
 */
export function addToMemory(
  memory: ClientMemory,
  summary: ConversationSummary
): ClientMemory {
  memory.conversationHistory.push(summary)
  // Garder max 20 conversations
  if (memory.conversationHistory.length > 20) {
    memory.conversationHistory = memory.conversationHistory.slice(-20)
  }
  memory.recentContext = buildRecentContext(memory.conversationHistory)
  memory.usageMetrics = buildUsageMetrics(memory.conversationHistory)
  return memory
}
