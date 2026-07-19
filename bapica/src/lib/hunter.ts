/**
 * Intégration Hunter.io — recherche d'emails professionnels par domaine (Domain Search).
 * Clé : HUNTER_API_KEY (Vercel). L'API Hunter est accessible dès le plan gratuit
 * (~25 requêtes/mois). Complémentaire d'Apollo : ici on part d'un domaine d'entreprise
 * et on récupère les personnes + emails réels.
 */
import type { Lead } from './apollo'

export function isHunterConfigured(): boolean {
  return Boolean(process.env.HUNTER_API_KEY)
}

/** Nettoie une saisie type "https://www.exemple.com/contact" → "exemple.com". */
export function cleanDomain(input: string): string {
  return input
    .trim()
    .replace(/^https?:\/\//i, '')
    .replace(/^www\./i, '')
    .replace(/\/.*$/, '')
    .toLowerCase()
}

export async function domainSearch(
  domain: string,
  limit = 10
): Promise<{ leads: Lead[]; total: number }> {
  const key = process.env.HUNTER_API_KEY
  if (!key) throw new Error('HUNTER_NOT_CONFIGURED')

  const url = new URL('https://api.hunter.io/v2/domain-search')
  url.searchParams.set('domain', domain)
  url.searchParams.set('limit', String(Math.min(Math.max(limit, 1), 25)))
  url.searchParams.set('api_key', key)

  const res = await fetch(url.toString())
  if (!res.ok) {
    const txt = await res.text().catch(() => '')
    if (res.status === 401) throw new Error('HUNTER_UNAUTHORIZED')
    if (res.status === 429) throw new Error('HUNTER_RATE_LIMIT')
    throw new Error(`Hunter ${res.status}: ${txt.slice(0, 300)}`)
  }

  const data = await res.json()
  const org: string = data?.data?.organization || domain
  const emails: any[] = Array.isArray(data?.data?.emails) ? data.data.emails : []

  const leads: Lead[] = emails.map((e) => ({
    name: [e.first_name, e.last_name].filter(Boolean).join(' ') || 'Inconnu',
    title: e.position || e.department || '',
    company: org,
    location: '',
    linkedinUrl: e.linkedin || '',
    email: e.value || null,
    emailLocked: !e.value,
  }))

  return { leads, total: leads.length }
}
