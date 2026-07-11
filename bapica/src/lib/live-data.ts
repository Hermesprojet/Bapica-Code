/**
 * Intégrations externes temps réel
 * 
 * 1. Google My Business — concurrence locale
 * 2. Indeed/LinkedIn Jobs — tendances recrutement
 * 3. RSS/Newsletters sectorielles — veille automatique
 */

/**
 * 1. Google My Business — Analyse concurrence locale
 * Recherche les entreprises similaires dans une zone géographique
 * via l'API Google Places (gratuite jusqu'à 100K requêtes/mois)
 * 
 * Env var: GOOGLE_PLACES_API_KEY
 */
export async function searchLocalCompetitors(
  sector: string,
  location: string
): Promise<string> {
  const apiKey = process.env.GOOGLE_PLACES_API_KEY
  if (!apiKey) return ''

  try {
    const query = encodeURIComponent(`${sector} ${location}`)
    const res = await fetch(
      `https://maps.googleapis.com/maps/api/place/textsearch/json?query=${query}&type=business&language=fr&key=${apiKey}`,
      { next: { revalidate: 3600 } }
    )
    const data = await res.json()

    if (!data.results?.length) return ''

    const competitors = data.results.slice(0, 5).map((p: any) =>
      `- ${p.name} (note: ${p.rating || '?'}/5, ${p.user_ratings_total || 0} avis) — ${p.formatted_address}`
    ).join('\n')

    return `\n--- Concurrence locale (Google) ---\n${competitors}\n`
  } catch {
    return ''
  }
}

/**
 * 2. Indeed/LinkedIn Jobs — Tendances recrutement temps réel
 * 
 * Scrape Indeed pour détecter les offres d'emploi par secteur/zone
 * Permet à l'agent recrutement de connaître le marché en direct
 */
export async function searchJobTrends(
  role: string,
  location: string
): Promise<string> {
  try {
    const query = encodeURIComponent(`${role} ${location}`)
    // Utilise l'API publique RSS d'Indeed
    const res = await fetch(
      `https://rss.indeed.com/rss?q=${query}&l=${encodeURIComponent(location)}&limit=5`,
      { next: { revalidate: 7200 } }
    )
    const text = await res.text()

    if (!text.includes('<item>')) return ''

    // Extraire les titres des offres
    const titles = text.match(/<title>(?!.*Indeed)(.*?)<\/title>/g)
    if (!titles?.length) return ''

    const jobs = titles.slice(0, 5).map(t =>
      `- ${t.replace(/<\/?title>/g, '').trim()}`
    ).join('\n')

    return `\n--- Offres d'emploi récentes (Indeed) ---\n${jobs}\n`
  } catch {
    return ''
  }
}

/**
 * 3. Veille sectorielle automatisée via RSS
 * 
 * Flux RSS par secteur — résumés par l'IA
 * Sources: BFM Business, Les Echos, L'Usine Digitale, FrenchWeb
 */
const SECTOR_FEEDS: Record<string, string[]> = {
  tech: [
    'https://www.usine-digitale.fr/rss/',
    'https://www.frenchweb.fr/feed',
  ],
  retail: [
    'https://www.lsa-conso.fr/rss/',
  ],
  finance: [
    'https://www.agefi.fr/rss/',
  ],
  general: [
    'https://www.bfmtv.com/rss/news-economie/',
    'https://www.lesechos.fr/rss/',
  ],
}

export async function getSectorNews(sector: string): Promise<string> {
  const feeds = SECTOR_FEEDS[sector] || SECTOR_FEEDS.general
  const items: string[] = []

  for (const feed of feeds) {
    try {
      const res = await fetch(feed, { next: { revalidate: 3600 } })
      const text = await res.text()
      const titles = text.match(/<title>(?!.*RSS)(.*?)<\/title>/g)
      if (titles) {
        items.push(...titles.slice(0, 3).map(t =>
          t.replace(/<\/?title>/g, '').replace(/<!\[CDATA\[|\]\]>/g, '').trim()
        ))
      }
    } catch {}
  }

  if (!items.length) return ''

  return `\n--- Actualités du secteur — ${new Date().toLocaleDateString('fr')} ---\n${items.map(i => `• ${i}`).join('\n')}\n`
}
