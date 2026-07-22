/**
 * Optimisations Bapica — streaming, cache, router, compression
 */

import Anthropic from '@anthropic-ai/sdk'

// Cache RAG — questions fréquentes → réponse instantanée (<10ms)
const ragCache = new Map<string, { result: string; timestamp: number }>()
const CACHE_TTL = 30 * 60 * 1000 // 30 min
const MAX_CACHE = 500

export function getCachedRAG(key: string): string | null {
  const entry = ragCache.get(key)
  if (entry && Date.now() - entry.timestamp < CACHE_TTL) return entry.result
  ragCache.delete(key)
  return null
}

export function setCachedRAG(key: string, result: string) {
  if (ragCache.size >= MAX_CACHE) {
    const oldest = [...ragCache.entries()].sort((a, b) => a[1].timestamp - b[1].timestamp)[0]
    if (oldest) ragCache.delete(oldest[0])
  }
  ragCache.set(key, { result, timestamp: Date.now() })
}

// Cache clé = agent + question simplifiée
export function ragCacheKey(agentId: string, question: string): string {
  return `${agentId}:${question.toLowerCase().trim().slice(0, 80)}`
}

/**
 * Routeur intelligent — détecte si la question est simple (Haiku suffit)
 * vs complexe (besoin de Sonnet)
 */
export function getOptimalModel(
  agentId: string,
  message: string
): { model: string; maxTokens: number } {
  const msg = message.toLowerCase().trim()

  // ── Bavardage strictement trivial → Haiku ──────────────────────────────────
  // ANCIENNE VERSION BUGUÉE : les motifs « simples » incluaient /^(quoi|comment)/
  // et /(prix|tarif|plan|formule)/ NON ancré. Résultat : « Comment structurer ma
  // prospection ? » ou « Quelle stratégie de prix ? » partaient en Haiku — la
  // majorité des vraies questions métier étaient donc traitées par le petit modèle.
  // Désormais : uniquement salutations / accusés de réception, ET message court.
  const trivialPatterns = [
    /^(bonjour|bonsoir|salut|hello|hey|coucou)\b/,
    /^(merci|thanks|super|parfait|nickel|ok|d'accord|entendu|compris)\b/,
    /^(oui|non|yes|no)\b/,
  ]
  if (msg.length <= 60 && trivialPatterns.some(p => p.test(msg))) {
    return { model: 'claude-haiku-4-5', maxTokens: 500 }
  }

  // ── Agents à enjeu élevé → toujours Sonnet ────────────────────────────────
  const criticalAgents = ['legal', 'accounting', 'prospection-strategie', 'general']
  if (criticalAgents.includes(agentId)) {
    return { model: 'claude-sonnet-4-5', maxTokens: 3000 }
  }

  // ── Signaux de complexité explicites → Sonnet ─────────────────────────────
  const complexPatterns = [
    /(stratégie|stratégique|business plan|levée de fonds|roadmap)/,
    /(analyse|analyser|diagnostic|audit|deep dive|approfondi|compare)/,
    /(juridique|contrat|conformité|rgpd|avocat|clause|litige)/,
    /(fiscal|impôt|tva|déclaration|comptable|trésorerie|prévision|budget)/,
    /(négocie|négociation|objection|closing)/,
    /(scale|scaling|croissance|expansion|recrut|embauche)/,
    /(pourquoi|explique|conseil|recommand|optimis|améliorer|structurer)/,
    /(marché|concurrent|positionnement|pricing|prix de vente)/,
  ]
  if (complexPatterns.some(p => p.test(msg))) {
    return { model: 'claude-sonnet-4-5', maxTokens: 2500 }
  }

  // ── Par défaut : Sonnet ───────────────────────────────────────────────────
  // L'ancien défaut basculait tout message < 200 caractères vers Haiku, alors
  // qu'une question métier courte (« Comment augmenter mon CA ? ») mérite le
  // meilleur raisonnement. Seul le bavardage trivial (traité plus haut) reste sur
  // Haiku ; tout le reste passe sur Sonnet.
  return { model: 'claude-sonnet-4-5', maxTokens: 2000 }
}

/**
 * Compression de prompt — réduit les tokens pour baisser le coût
 */
export function compressPrompt(prompt: string, _agentId: string): string {
  // Normalisation des espaces uniquement (sans perte d'information).
  //
  // ⚠️ NE PAS réintroduire de troncature par regex ici. Une ancienne version
  // remplaçait /RÈGLES\s*:[\s\S]*?(?=\n\n|$)/ pour les agents support/general/content :
  // le prompt étant assemblé avec des sauts de ligne SIMPLES (aucun "\n\n"), la regex
  // matchait jusqu'à la FIN du prompt et supprimait toutes les règles suivantes
  // (prose sans Markdown, pas d'émojis, longueur, et les garde-fous « capacités Bapica »).
  // Symptôme observé : Camille (content) répondait en Markdown avec émojis et listes.
  return prompt
    .replace(/\n{3,}/g, '\n\n')
    .replace(/ {2,}/g, ' ')
    .trim()
}

/**
 * Extraction de livrables — quand Claude répond, détecte et formate les livrables
 */
export function extractDeliverables(
  response: string,
  type?: 'email' | 'devis' | 'contrat' | 'rapport' | 'linkedin'
): { main: string; deliverable?: { type: string; content: string; format: string } } {
  // Détecter les blocs de code markdown (```)
  const codeBlock = response.match(/```(\w+)?\n?([\s\S]*?)```/)
  if (codeBlock) {
    const format = codeBlock[1] || 'txt'
    return {
      main: response.replace(codeBlock[0], ''),
      deliverable: { type: format, content: codeBlock[2].trim(), format },
    }
  }

  // Détecter les sections "--- LIVRABLE ---" si le prompt le demande
  const deliverableMatch = response.match(/---\s*LIVRABLE\s*---\n?([\s\S]*?)(?:$|---)/)
  if (deliverableMatch) {
    return {
      main: response.replace(deliverableMatch[0], ''),
      deliverable: { type: type || 'texte', content: deliverableMatch[1].trim(), format: 'txt' },
    }
  }

  return { main: response }
}

/**
 * Cache memoization pour les appels RAG
 * Même question + même agent dans les 30min → réponse instantanée
 */
const ragMemo = new Map<string, { data: string; ts: number }>()

export function memoizeRAG(key: string, fn: () => Promise<string>): Promise<string> {
  const cached = ragMemo.get(key)
  if (cached && Date.now() - cached.ts < CACHE_TTL) {
    return Promise.resolve(cached.data)
  }
  return fn().then(data => {
    if (ragMemo.size > 500) ragMemo.clear()
    ragMemo.set(key, { data, ts: Date.now() })
    return data
  })
}
