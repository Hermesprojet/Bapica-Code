/**
 * Agent Orchestrator — Léo détecte le besoin et route vers le spécialiste
 * 
 * Chaînage automatique = l'utilisateur parle, 
 * l'orchestrateur analyse et suggère le meilleur agent.
 */

export interface AgentRouting {
  agentId: string
  reason: string
  confidence: number
}

// Patterns de détection par mots-clés
const AGENT_PATTERNS: Record<string, { keywords: string[]; weight: number }> = {
  'prospection-strategie': { keywords: ['prospect', 'client', 'vente', 'commercial', 'ca', 'lead', 'pipeline', 'closing', 'chiffre', 'marché', 'concurrence', 'veille', 'secteur', 'tendance'], weight: 1 },
  support: { keywords: ['bug', 'problème', 'erreur', 'marche pas', 'panne', 'aide', 'help'], weight: 1 },
  recruiter: { keywords: ['recruter', 'embauche', 'cv', 'candidat', 'entretien', 'poste', 'offre emploi'], weight: 1 },
  legal: { keywords: ['contrat', 'juridique', 'loi', 'avocat', 'rgpd', 'conformité', 'litige'], weight: 0.9 },
  accounting: { keywords: ['compta', 'facture', 'tva', 'trésorerie', 'bilan', 'fiscal', 'déclaration', 'kpi', 'tableau bord'], weight: 0.9 },
}

export function detectAgentIntent(message: string, currentAgentId: string): AgentRouting[] {
  const msg = message.toLowerCase()
  const scores: AgentRouting[] = []

  for (const [agentId, { keywords, weight }] of Object.entries(AGENT_PATTERNS)) {
    if (agentId === currentAgentId) continue
    let score = 0
    for (const kw of keywords) {
      if (msg.includes(kw)) score += weight
    }
    if (score > 0) {
      scores.push({ agentId, reason: `Mots-clés: ${keywords.filter(k => msg.includes(k)).join(', ')}`, confidence: Math.min(score / keywords.length, 1) })
    }
  }

  return scores.sort((a, b) => b.confidence - a.confidence).slice(0, 3)
}

/**
 * Formatte une suggestion de routing pour l'utilisateur
 */
export function formatRoutingSuggestion(routes: AgentRouting[]): string {
  if (!routes.length) return ''
  const top = routes[0]
  return `\n💡 ${top.reason ? `Détecté: ${top.reason}. ` : ''}L'agent **${top.agentId}** serait plus pertinent pour cette question.`
}
