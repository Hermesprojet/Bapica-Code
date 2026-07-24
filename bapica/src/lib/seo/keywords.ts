// Recherche de mots-clés RÉELLE via Google Suggest (autocomplétion) — gratuit, sans clé API.
// Donne les requêtes réellement tapées par les internautes autour d'un mot-clé de départ :
// longue traîne, questions, intentions d'achat. Base de la stratégie SEO de Camille.

const SUGGEST = 'https://suggestqueries.google.com/complete/search'

async function suggest(query: string, lang: string): Promise<string[]> {
  try {
    const url = `${SUGGEST}?client=firefox&hl=${encodeURIComponent(lang)}&q=${encodeURIComponent(query)}`
    const res = await fetch(url, { headers: { 'User-Agent': 'BapicaSEOBot/1.0' }, signal: AbortSignal.timeout(6000) })
    if (!res.ok) return []
    const data = await res.json().catch(() => null)
    // Format : [query, [suggestions...], ...]
    return Array.isArray(data) && Array.isArray(data[1]) ? data[1].map(String) : []
  } catch {
    return []
  }
}

/**
 * Élargit un mot-clé de départ en une liste de suggestions dédupliquées, en interrogeant
 * l'autocomplétion sur le terme seul + des modificateurs d'intention (comment, prix, avis…).
 */
export async function researchKeywords(seed: string, lang = 'fr'): Promise<{ ok: boolean; seed: string; keywords: string[]; questions: string[]; error?: string }> {
  const base = (seed || '').trim()
  if (!base) return { ok: false, seed, keywords: [], questions: [], error: 'Mot-clé de départ manquant.' }

  const questionWords = lang.startsWith('en')
    ? ['how', 'what', 'why', 'best', 'vs']
    : ['comment', 'pourquoi', 'quel', 'meilleur', 'avis']
  const modifiers = lang.startsWith('en')
    ? [base, `${base} `, `${base} price`, `${base} best`, ...questionWords.map((w) => `${w} ${base}`)]
    : [base, `${base} `, `${base} prix`, `${base} avis`, ...questionWords.map((w) => `${w} ${base}`)]

  const results = await Promise.all(modifiers.map((m) => suggest(m, lang)))
  const all = results.flat().map((k) => k.trim()).filter(Boolean)

  // Dédupe (insensible à la casse) en conservant l'ordre.
  const seen = new Set<string>()
  const unique: string[] = []
  for (const k of all) {
    const low = k.toLowerCase()
    if (!seen.has(low)) { seen.add(low); unique.push(k) }
  }
  if (unique.length === 0) return { ok: false, seed: base, keywords: [], questions: [], error: 'Aucune suggestion (source indisponible).' }

  const qWords = new RegExp(`^(${questionWords.join('|')})\\b`, 'i')
  const questions = unique.filter((k) => qWords.test(k)).slice(0, 15)
  const keywords = unique.slice(0, 40)
  return { ok: true, seed: base, keywords, questions }
}
