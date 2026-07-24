/**
 * Intégration Apify — prospection LOCALE via l'actor Google Maps
 * (compass/crawler-google-places). Complémentaire d'Apollo (contacts B2B par poste) et
 * de Hunter (emails par domaine) : ici on récupère des ÉTABLISSEMENTS locaux avec leur
 * TÉLÉPHONE et leur site — idéal pour les TPE/commerces/artisans, cœur de cible de Bapica.
 *
 * Clé : APIFY_TOKEN (Vercel). Sans clé → isApifyConfigured() = false (pas de crash).
 * Périmètre volontairement limité à Google Maps (données d'entreprises, risque faible) ;
 * pas de scraping LinkedIn (CGU + RGPD sur données personnelles).
 *
 * Écrit sans pouvoir tester en sandbox : en cas d'échec API, l'erreur brute est remontée.
 */

export interface MapsLead {
  name: string
  category: string
  address: string
  phone: string | null
  website: string | null
  rating: number | null
  reviews: number | null
}

export function isApifyConfigured(): boolean {
  return Boolean(process.env.APIFY_TOKEN)
}

/**
 * Recherche des établissements locaux (secteur + ville) via Google Maps.
 * NB : le scraping prend du temps — on borne le nombre de résultats et on coupe à 150 s.
 * En environnement serverless court, préférer des recherches ciblées (peu de résultats).
 */
export async function searchLocalBusinesses(opts: {
  sector: string
  city: string
  limit?: number
}): Promise<{ leads: MapsLead[]; total: number }> {
  const token = process.env.APIFY_TOKEN
  if (!token) throw new Error('APIFY_NOT_CONFIGURED')

  const limit = Math.min(Math.max(opts.limit || 15, 1), 40)
  const search = `${opts.sector} ${opts.city}`.trim()

  const res = await fetch(
    `https://api.apify.com/v2/acts/compass~crawler-google-places/run-sync-get-dataset-items?token=${encodeURIComponent(token)}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        searchStringsArray: [search],
        maxCrawledPlacesPerSearch: limit,
        language: 'fr',
        skipClosedPlaces: true,
      }),
      signal: AbortSignal.timeout(150000),
    }
  )

  if (!res.ok) {
    const txt = await res.text().catch(() => '')
    if (res.status === 401) throw new Error('APIFY_UNAUTHORIZED')
    throw new Error(`Apify ${res.status}: ${txt.slice(0, 300)}`)
  }

  const data = await res.json()
  const places: any[] = Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : []

  const leads: MapsLead[] = places.map((p) => ({
    name: p.title || p.name || 'Inconnu',
    category: p.categoryName || (Array.isArray(p.categories) ? p.categories[0] : '') || '',
    address: p.address || [p.street, p.city].filter(Boolean).join(', ') || '',
    phone: p.phone || p.phoneUnformatted || null,
    website: p.website || p.url || null,
    rating: typeof p.totalScore === 'number' ? p.totalScore : null,
    reviews: typeof p.reviewsCount === 'number' ? p.reviewsCount : null,
  }))

  return { leads, total: leads.length }
}
