/**
 * Fable-Powered Prompts pour Modèles Légers
 * 
 * Les patterns Claude Fable 5 appliqués à des modèles économiques
 * (Haiku, GPT-4o-mini, Deepseek) pour un rendement élevé à petit prix.
 * 
 * Économie estimée : 10-20x moins cher que Sonnet/Opus
 */

// ============================================================
// COMPARAISON COÛTS (par million de tokens)
// ============================================================

/*
Modèle              Input      Output     Ratio vs Sonnet
─────────────────────────────────────────────────────────
Claude Opus 4.8     $15.00     $75.00     5x plus cher
Claude Sonnet 4.6    $3.00     $15.00     1x (référence)
Claude Fable 5      $15.00     $75.00     5x plus cher
Claude Haiku 4.5     $0.80      $4.00     0.25x (4x moins cher)
GPT-4o-mini          $0.15      $0.60     0.05x (20x moins cher)
Deepseek V3          $0.27      $1.10     0.07x (14x moins cher)

Stratégie Bapica :
- Agent Coordinateur (Léo) → Sonnet (qualité max)
- Analystes (Compta, Juridique, Analytics) → Sonnet (précision)
- Spécialistes (Support, Contenu, Prospection) → Haiku + Fable patterns
- Chat démo public → Haiku + Fable patterns
*/

// ============================================================
// PATTERNS FABLE OPTIMISÉS POUR MODÈLES LÉGERS
// ============================================================

export const FABLE_LITE_SYSTEM_PROMPT = `
Tu es un agent IA professionnel. Suis ces règles de comportement :

1. PARLE EN PROSE NATURELLE — jamais de listes à puces, jamais de formatting. Comme un expert qui dialogue.

2. MÉMOIRE NATURELLE — intègre le contexte sans JAMAIS dire "je vois que", "d'après ton profil", "selon tes données". Les infos sur le client sont implicites, pas des stats à réciter.

3. TON — chaleureux mais direct. Dis la vérité avec tact. Pas d'émojis. 4-6 phrases max.

4. REFUS ÉLÉGANTS — explique le principe sans détailler la mécanique du refus.

5. CONNAISSANCE PRODUIT — tu connais Bapica : 13 agents, plans 49€ et 79€, 15 jours d'essai.

6. ADAPTATION — ajuste ton niveau de détail à la maturité du client. Simple pour débutant, technique pour expert.

7. NE CRÉE PAS DE DÉPENDANCE — tu es un outil, pas un substitut aux relations humaines.
`

// Version ultra-compacte (moins de tokens = moins cher)
export const FABLE_MINI_SYSTEM_PROMPT = `
Règles : prose naturelle sans listes, intègre le contexte sans dire "je vois que", ton chaleureux direct, 4-6 phrases, pas d'émojis, connais Bapica (13 agents, 49€/79€, 15j essai).
`

// ============================================================
// MATRICE DE ROUTAGE INTELLIGENT
// ============================================================

export type ModelTier = 'fable' | 'sonnet' | 'haiku' | 'mini'

interface RoutingRule {
  agentTypes: string[]
  taskComplexity: 'low' | 'medium' | 'high'
  model: ModelTier
  estimatedCostPer1k: number
}

export const ROUTING_MATRIX: RoutingRule[] = [
  // Coordinateur — toujours Sonnet (qualité max)
  { agentTypes: ['general'], taskComplexity: 'high', model: 'sonnet', estimatedCostPer1k: 0.018 },
  { agentTypes: ['general'], taskComplexity: 'medium', model: 'sonnet', estimatedCostPer1k: 0.018 },
  { agentTypes: ['general'], taskComplexity: 'low', model: 'sonnet', estimatedCostPer1k: 0.018 },
  
  // Analystes — Sonnet pour précision
  { agentTypes: ['accounting', 'legal', 'analytics', 'scaling'], taskComplexity: 'high', model: 'sonnet', estimatedCostPer1k: 0.018 },
  { agentTypes: ['accounting', 'legal', 'analytics', 'scaling'], taskComplexity: 'medium', model: 'sonnet', estimatedCostPer1k: 0.018 },
  { agentTypes: ['accounting', 'legal', 'analytics', 'scaling'], taskComplexity: 'low', model: 'haiku', estimatedCostPer1k: 0.004 },
  
  // Spécialistes — Haiku + Fable patterns (80% de la qualité, 25% du prix)
  { agentTypes: ['support', 'content', 'prospector', 'closer', 'telephone', 'video', 'recruiter', 'trends'], taskComplexity: 'high', model: 'haiku', estimatedCostPer1k: 0.004 },
  { agentTypes: ['support', 'content', 'prospector', 'closer', 'telephone', 'video', 'recruiter', 'trends'], taskComplexity: 'medium', model: 'haiku', estimatedCostPer1k: 0.004 },
  { agentTypes: ['support', 'content', 'prospector', 'closer', 'telephone', 'video', 'recruiter', 'trends'], taskComplexity: 'low', model: 'mini', estimatedCostPer1k: 0.0006 },
  
  // Demo chat — Mini (public, gratuit)
  { agentTypes: ['demo'], taskComplexity: 'low', model: 'mini', estimatedCostPer1k: 0.0006 },
]

export function routeModel(agentType: string, messageLength: number): ModelTier {
  const complexity = messageLength > 200 ? 'high' : messageLength > 80 ? 'medium' : 'low'
  
  const rule = ROUTING_MATRIX.find(
    r => r.agentTypes.includes(agentType) && r.taskComplexity === complexity
  )
  
  return rule?.model || 'haiku'
}

// ============================================================
// PROMPT BUILDER — injecte les patterns Fable dans n'importe quel modèle
// ============================================================

export function buildFablePrompt(
  basePrompt: string,
  modelTier: ModelTier,
  clientContext?: string
): string {
  // Version courte pour modèles légers (moins de tokens = moins cher + plus rapide)
  const fableCore = modelTier === 'mini' 
    ? FABLE_MINI_SYSTEM_PROMPT 
    : FABLE_LITE_SYSTEM_PROMPT

  const parts = [basePrompt, fableCore]
  
  if (clientContext) {
    parts.push(`\nContexte : ${clientContext}`)
  }
  
  return parts.join('\n\n')
}

// ============================================================
// ESTIMATEUR DE COÛTS
// ============================================================

export interface CostEstimate {
  model: ModelTier
  inputTokens: number
  outputTokens: number
  cost: number
  savingsVsSonnet: number
}

export function estimateCost(
  model: ModelTier, 
  inputTokens: number, 
  outputTokens: number
): CostEstimate {
  const rates: Record<ModelTier, { input: number; output: number }> = {
    fable: { input: 15.00, output: 75.00 },
    sonnet: { input: 3.00, output: 15.00 },
    haiku: { input: 0.80, output: 4.00 },
    mini: { input: 0.15, output: 0.60 },
  }
  
  const r = rates[model]
  const inputCost = (inputTokens / 1_000_000) * r.input
  const outputCost = (outputTokens / 1_000_000) * r.output
  const total = inputCost + outputCost
  
  const sonnetCost = (inputTokens / 1_000_000) * 3.00 + (outputTokens / 1_000_000) * 15.00
  
  return {
    model,
    inputTokens,
    outputTokens,
    cost: Math.round(total * 10000) / 10000,
    savingsVsSonnet: Math.round((1 - total / sonnetCost) * 100),
  }
}

// ============================================================
// EXEMPLE : Coût comparé pour 1000 conversations/mois
// ============================================================

/*
Scénario : 1000 conversations/mois, 500 tokens input, 200 tokens output chacune

Modèle              Coût/mois     Économie vs Sonnet
─────────────────────────────────────────────────────
Tout Sonnet          2.25€        0% (référence)
Tout Haiku           0.56€        75% d'économie
Tout Mini            0.09€        96% d'économie
Routing intelligent  0.95€        58% d'économie

Avec routing intelligent :
- Léo + Analystes (30% des requêtes) → Sonnet = 0.68€
- Spécialistes (50% des requêtes) → Haiku = 0.28€  
- Chat démo (20% des requêtes) → Mini = 0.02€
TOTAL = 0.98€/mois pour 1000 conversations
*/
