/**
 * Bapica Cortex — Intelligence avancée
 * 
 * Intègre TOUTES les propositions Claude + Deepseek :
 * 1. Mémoire persistante vectorielle
 * 2. Mode prédictif & alertes proactives
 * 3. Auto-pilote multi-agents
 * 4. Multi-modèle natif intelligent
 * 5. ROI Dashboard
 * 6. Apprentissage par renforcement
 * 7. Simulation what-if
 * 8. Voice-first
 */

// ─── 1. MÉMOIRE PERSISTANTE VECTORIELLE ───────────────────

export interface LongTermMemory {
  id: string
  userId: string
  content: string
  embedding?: number[]
  type: 'decision' | 'preference' | 'fact' | 'goal' | 'feedback'
  importance: number
  timestamp: string
  context: string
}

/**
 * Bapica se souvient de tout, 6 mois plus tard.
 * "La dernière fois tu m'as dit que ton CA était de 1.2M€"
 */
export function buildMemoryPrompt(memories: LongTermMemory[]): string {
  if (!memories.length) return ''

  const recent = memories
    .sort((a, b) => b.importance - a.importance)
    .slice(0, 10)

  return [
    '\n--- MÉMOIRE PERSISTANTE ---',
    'Tu te souviens de ces informations sur ce client :',
    ...recent.map(m => {
      const date = new Date(m.timestamp).toLocaleDateString('fr')
      return `- [${date}] ${m.content} (${m.type})`
    }),
    '---\n',
  ].join('\n')
}

// ─── 2. MODE PRÉDICTIF & ALERTES PROACTIVES ────────────────

export interface PredictiveAlert {
  type: 'opportunity' | 'risk' | 'reminder' | 'anomaly'
  title: string
  description: string
  agentRecommended: string
  urgency: 'low' | 'medium' | 'high'
  action: string
}

/**
 * Bapica anticipe les besoins avant qu'on les exprime.
 * "3 de vos clients sont inactifs depuis 15 jours"
 * "Votre trésorerie sera tendue dans 3 semaines"
 */
export function generatePredictiveAlerts(
  profile: any,
  activity: { lastLogin: string; messagesCount: number }
): PredictiveAlert[] {
  const alerts: PredictiveAlert[] = []

  // Inactivité
  const daysSinceLastLogin = profile.lastLogin
    ? Math.floor((Date.now() - new Date(profile.lastLogin).getTime()) / 86400000)
    : 0
  if (daysSinceLastLogin > 7) {
    alerts.push({
      type: 'reminder',
      title: 'Absence détectée',
      description: `Vous n'avez pas consulté Bapica depuis ${daysSinceLastLogin} jours. Vos concurrents avancent.`,
      agentRecommended: 'prospection-strategie',
      urgency: 'medium',
      action: 'Reprendre le suivi commercial',
    })
  }

  // Trésorerie
  if (profile.revenue?.includes('100K') || profile.revenue?.includes('<')) {
    alerts.push({
      type: 'risk',
      title: 'Trésorerie à surveiller',
      description: 'Votre CA est modeste. Un imprévu peut mettre en danger votre activité.',
      agentRecommended: 'accounting',
      urgency: 'high',
      action: 'Analyser la trésorerie',
    })
  }

  // Croissance
  if (profile.employee_count === '16-50' && !profile.crm) {
    alerts.push({
      type: 'opportunity',
      title: 'Maturité détectée — besoin CRM',
      description: 'À votre taille, un CRM augmente le CA de 29% en moyenne.',
      agentRecommended: 'prospection-strategie',
      urgency: 'medium',
      action: 'Évaluer les CRM',
    })
  }

  // Juridique
  if (!profile.websiteHasLegalPages) {
    alerts.push({
      type: 'risk',
      title: '⚠️ Risque juridique — Mentions légales absentes',
      description: 'Votre site n\'a pas de mentions légales. Amende possible jusqu\'à 75 000€.',
      agentRecommended: 'legal',
      urgency: 'high',
      action: 'Rédiger les mentions légales',
    })
  }

  return alerts.sort((a, b) => {
    const urgency = { high: 3, medium: 2, low: 1 }
    return urgency[b.urgency] - urgency[a.urgency]
  })
}

// ─── 3. AUTO-PILOTE MULTI-AGENTS ───────────────────────────

export interface AutopilotGoal {
  id: string
  userId: string
  goal: string
  targetDate?: string
  progress: number
  agents: { agentId: string; task: string; status: 'pending' | 'active' | 'done' }[]
  createdAt: string
}

/**
 * Le dirigeant donne un objectif.
 * Bapica orchestre TOUS les agents vers ce but.
 * 
 * Ex: "+30% de CA cette année"
 * → Agent Croissance: plan d'acquisition
 * → Agent Analytics: KPIs à suivre
 * → Agent Compta: projection trésorerie
 * → Agent Support: améliorer la rétention
 */
export function orchestrateGoal(goal: string, profile: any): AutopilotGoal {
  const agents: AutopilotGoal['agents'] = []

  if (goal.match(/ca|chiffre|croissance|vente|client/i)) {
    agents.push(
      { agentId: 'prospection-strategie', task: 'Plan d\'acquisition clients et croissance CA', status: 'pending' },
      { agentId: 'analytics', task: 'Mise en place des KPIs de suivi', status: 'pending' },
      { agentId: 'support', task: 'Optimisation de la rétention client', status: 'pending' },
    )
  }

  if (goal.match(/recruter|équipe|embauche/i)) {
    agents.push(
      { agentId: 'recruiter', task: 'Stratégie de recrutement et fiches de poste', status: 'pending' },
      { agentId: 'legal', task: 'Vérification des contrats de travail', status: 'pending' },
      { agentId: 'accounting', task: 'Budget recrutement et charges', status: 'pending' },
    )
  }

  if (goal.match(/trésorerie|rentab|marge|coût/i)) {
    agents.push(
      { agentId: 'accounting', task: 'Audit des dépenses et optimisation fiscale', status: 'pending' },
      { agentId: 'analytics', task: 'Analyse de rentabilité par produit/client', status: 'pending' },
      { agentId: 'prospection-strategie', task: 'Ajustement des prix et marges', status: 'pending' },
    )
  }

  if (goal.match(/conformité|juridique|rgpd|contrat/i)) {
    agents.push(
      { agentId: 'legal', task: 'Audit de conformité complet', status: 'pending' },
      { agentId: 'support', task: 'Mise à jour CGV et politique confidentialité', status: 'pending' },
    )
  }

  // Si aucun pattern reconnu, activer les agents généraux
  if (!agents.length) {
    agents.push(
      { agentId: 'general', task: 'Analyse de votre objectif', status: 'pending' },
      { agentId: 'trends', task: 'Veille sur les opportunités liées', status: 'pending' },
    )
  }

  return {
    id: `goal_${Date.now()}`,
    userId: profile.companyName || 'unknown',
    goal,
    progress: 0,
    agents: agents.slice(0, 5),
    createdAt: new Date().toISOString(),
  }
}

// ─── 4. MULTI-MODÈLE NATIF INTELLIGENT ─────────────────────

export type ModelTier = 'fast' | 'balanced' | 'powerful'

export interface ModelDecision {
  tier: ModelTier
  model: string
  costFactor: number
  latencyMs: number
  reasoning: string
}

/**
 * Bapica choisit automatiquement le bon modèle :
 * - Simple (bonjour, oui/non) → Haiku (0.01€)
 * - Normal (conseil, analyse) → Sonnet (0.05€)
 * - Critique (stratégie, juridique) → Opus (0.15€)
 */
export function selectOptimalModel(
  message: string,
  agentId: string,
  conversationHistory: number
): ModelDecision {
  const msg = message.toLowerCase()
  const length = msg.length

  // Critique → toujours le plus puissant
  if (agentId === 'legal' || agentId === 'accounting') {
    return { tier: 'powerful', model: 'claude-opus-4-1', costFactor: 1.5, latencyMs: 3000, reasoning: 'Agent critique — précision prioritaire' }
  }

  // Conversation longue → contexte riche → modèle équilibré
  if (conversationHistory > 5) {
    return { tier: 'balanced', model: 'claude-sonnet-4-5', costFactor: 1.0, latencyMs: 1500, reasoning: 'Contexte conversation riche' }
  }

  // Message court et simple
  if (length < 30 || msg.match(/^(bonjour|salut|merci|ok|oui|non|bye)/)) {
    return { tier: 'fast', model: 'claude-haiku-4-5', costFactor: 0.2, latencyMs: 500, reasoning: 'Message simple — réponse rapide' }
  }

  // Message moyen
  if (length < 200) {
    return { tier: 'balanced', model: 'claude-sonnet-4-5', costFactor: 1.0, latencyMs: 1500, reasoning: 'Besoin standard' }
  }

  // Message long = question complexe
  return { tier: 'powerful', model: 'claude-sonnet-4-5', costFactor: 1.0, latencyMs: 1500, reasoning: 'Question détaillée' }
}

// ─── 5. ROI DASHBOARD ──────────────────────────────────────

export interface ROIMetrics {
  timeSavedMinutes: number
  moneyEquivalent: number
  tasksCompleted: number
  insightsGenerated: number
  agentsUsed: { agentId: string; count: number }[]
  topWin: string
}

/**
 * Calcule le ROI pour le client
 * "Ce mois-ci, Bapica vous a fait économiser 47h et +12K€"
 */
export function calculateROI(usage: {
  messagesCount: number
  agentsUsed: string[]
  problemsResolved: number
  profile: any
}): ROIMetrics {
  const hourlyRate = 75 // Taux horaire moyen PME
  const timePerMessage = 5 // minutes économisées par message
  const timePerProblem = 30 // minutes économisées par problème résolu

  const timeSaved = usage.messagesCount * timePerMessage + usage.problemsResolved * timePerProblem
  const moneyEquivalent = Math.round((timeSaved / 60) * hourlyRate)

  const agentCounts = usage.agentsUsed.reduce((acc, id) => {
    acc[id] = (acc[id] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  return {
    timeSavedMinutes: timeSaved,
    moneyEquivalent,
    tasksCompleted: usage.messagesCount,
    insightsGenerated: usage.problemsResolved,
    agentsUsed: Object.entries(agentCounts).map(([id, count]) => ({ agentId: id, count })),
    topWin: moneyEquivalent > 500
      ? `+${moneyEquivalent}€ de valeur créée ce mois`
      : 'Commencez à utiliser Bapica régulièrement pour voir le ROI',
  }
}

// ─── 6. APPRENTISSAGE PAR RENFORCEMENT ─────────────────────

export interface FeedbackSignal {
  messageId: string
  userId: string
  agentId: string
  rating: '👍' | '👎' | '⭐' | '💡'
  comment?: string
  ragMatches: string[]
  timestamp: string
}

/**
 * Chaque 👍/👎 ajuste le poids des fiches RAG.
 * Les bonnes montent, les mauvaises tombent.
 */
const feedbackWeights = new Map<string, number>()

export function applyFeedback(feedback: FeedbackSignal) {
  for (const matchId of feedback.ragMatches) {
    const current = feedbackWeights.get(matchId) || 1.0
    if (feedback.rating === '👍' || feedback.rating === '⭐') {
      feedbackWeights.set(matchId, current * 1.1) // +10%
    } else if (feedback.rating === '👎') {
      feedbackWeights.set(matchId, current * 0.8) // -20%
    }
  }
}

export function getFeedbackWeight(ragId: string): number {
  return feedbackWeights.get(ragId) || 1.0
}

// ─── 7. SIMULATION WHAT-IF ─────────────────────────────────

export interface SimulationRequest {
  scenario: string
  currentMetrics: {
    revenue: number
    employees: number
    margin: number
    clients: number
    avgPrice: number
  }
}

export interface SimulationResult {
  scenario: string
  impact: { metric: string; before: number; after: number; change: string }[]
  riskLevel: 'low' | 'medium' | 'high'
  recommendation: string
}

/**
 * "Si j'augmente mes prix de 15%, que se passe-t-il ?"
 * Bapica simule avec les données réelles du client.
 */
export function simulateScenario(request: SimulationRequest): SimulationResult {
  const m = request.currentMetrics
  const scenario = request.scenario.toLowerCase()
  const impact: SimulationResult['impact'] = []

  // Hausse de prix
  if (scenario.match(/augment.*prix|hausse.*tarif|augmenter.*tarif/)) {
    const increase = extractPercentage(scenario) || 10
    const newPrice = m.avgPrice * (1 + increase / 100)
    const potentialLoss = Math.round(m.clients * 0.05) // ~5% de clients perdus
    const newRevenue = Math.round((m.clients - potentialLoss) * newPrice * 12)
    const currentRevenue = Math.round(m.clients * m.avgPrice * 12)

    impact.push(
      { metric: 'Prix moyen', before: m.avgPrice, after: Math.round(newPrice), change: `+${increase}%` },
      { metric: 'Clients estimés', before: m.clients, after: m.clients - potentialLoss, change: `-${potentialLoss}` },
      { metric: 'CA annuel estimé', before: currentRevenue, after: newRevenue, change: `${newRevenue > currentRevenue ? '+' : '-'}${Math.abs(newRevenue - currentRevenue)}€` },
    )

    return {
      scenario: `Hausse de prix de ${increase}%`,
      impact,
      riskLevel: increase > 10 ? 'high' : 'medium',
      recommendation: newRevenue > currentRevenue
        ? `✅ Rentable: +${newRevenue - currentRevenue}€/an. Allez-y progressivement.`
        : `⚠️ Risqué à ${increase}%. Testez d'abord à +5%.`,
    }
  }

  // Recrutement
  if (scenario.match(/recruter|embauche|nouveau.*employé/)) {
    const salaryCost = 45000 // coût annuel moyen
    const revenuePerEmployee = m.revenue / Math.max(m.employees, 1)
    const newRevenue = Math.round(m.revenue + revenuePerEmployee * 0.7) // hypothèse 70% rendement an 1

    impact.push(
      { metric: 'Coût annuel', before: 0, after: salaryCost, change: `+${salaryCost}€` },
      { metric: 'CA projeté', before: m.revenue, after: newRevenue, change: `${newRevenue > m.revenue ? '+' : '-'}${Math.abs(newRevenue - m.revenue)}€` },
    )

    return {
      scenario: 'Recrutement d\'un employé',
      impact,
      riskLevel: 'medium',
      recommendation: newRevenue > m.revenue + salaryCost
        ? '✅ Rentable dès l\'année 1. Investissez.'
        : '⚠️ Rentable à partir de l\'année 2. Assurez votre trésorerie.',
    }
  }

  return {
    scenario: request.scenario,
    impact: [{ metric: 'Scénario', before: 0, after: 0, change: 'Analyse IA nécessaire' }],
    riskLevel: 'low',
    recommendation: 'Décrivez votre scénario plus précisément (chiffres attendus).',
  }
}

function extractPercentage(text: string): number | null {
  const match = text.match(/(\d+)\s*%/);
  return match ? parseInt(match[1]) : null;
}

// ─── 8. VOICE-FIRST ────────────────────────────────────────

export interface VoiceCommand {
  transcript: string
  intent: 'question' | 'task' | 'emergency' | 'note'
  confidence: number
}

/**
 * Détecte l'intention d'une commande vocale
 */
export function parseVoiceIntent(transcript: string): VoiceCommand {
  const t = transcript.toLowerCase()

  if (t.match(/urgence|tout de suite|immédiatement|problème grave/i)) {
    return { transcript, intent: 'emergency', confidence: 0.85 }
  }

  if (t.match(/note|rappelle|pense-bête|noter|enregistrer/i)) {
    return { transcript, intent: 'note', confidence: 0.8 }
  }

  if (t.match(/fais|envoie|crée|génère|écris|lance|commande/i)) {
    return { transcript, intent: 'task', confidence: 0.75 }
  }

  return { transcript, intent: 'question', confidence: 0.7 }
}
