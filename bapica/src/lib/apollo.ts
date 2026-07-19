/**
 * Intégration Apollo.io — recherche de prospects B2B (People Search).
 * Clé requise : APOLLO_API_KEY (Vercel). Sans clé, isApolloConfigured() = false
 * et la route renvoie un message « en cours de configuration » (pas de crash).
 *
 * Écrit sans pouvoir tester en sandbox : en cas d'échec API, l'erreur brute est
 * remontée pour ajustement au 1er test réel.
 */

export interface LeadSearchFilters {
  titles?: string[] // postes visés (ex : "Directeur commercial")
  locations?: string[] // lieux (ex : "France", "Paris")
  keywords?: string // secteur / mots-clés libres
  employeeRanges?: string[] // ex : "1,10" | "11,50" | "51,200"
  page?: number
  perPage?: number
}

export interface Lead {
  name: string
  title: string
  company: string
  location: string
  linkedinUrl: string
  email: string | null
  emailLocked: boolean // true = email non révélé (nécessite un crédit d'enrichissement Apollo)
}

export function isApolloConfigured(): boolean {
  return Boolean(process.env.APOLLO_API_KEY)
}

export async function searchLeads(
  filters: LeadSearchFilters
): Promise<{ leads: Lead[]; total: number }> {
  const key = process.env.APOLLO_API_KEY
  if (!key) throw new Error('APOLLO_NOT_CONFIGURED')

  const body: Record<string, unknown> = {
    page: filters.page && filters.page > 0 ? filters.page : 1,
    per_page: Math.min(Math.max(filters.perPage || 10, 1), 25),
  }
  if (filters.titles?.length) body.person_titles = filters.titles
  if (filters.locations?.length) body.person_locations = filters.locations
  if (filters.keywords) body.q_keywords = filters.keywords
  if (filters.employeeRanges?.length) body.organization_num_employees_ranges = filters.employeeRanges

  const res = await fetch('https://api.apollo.io/api/v1/mixed_people/search', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-cache',
      'X-Api-Key': key,
    },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const txt = await res.text().catch(() => '')
    if (res.status === 403 && /free plan|not accessible|API_INACCESSIBLE/i.test(txt)) {
      throw new Error('APOLLO_PLAN_REQUIRED')
    }
    if (res.status === 401) {
      throw new Error('APOLLO_UNAUTHORIZED')
    }
    throw new Error(`Apollo ${res.status}: ${txt.slice(0, 300)}`)
  }

  const data = await res.json()
  const people: any[] = Array.isArray(data.people) ? data.people : []

  const leads: Lead[] = people.map((p) => {
    const rawEmail: string | null = p.email || null
    const locked = !rawEmail || String(rawEmail).includes('email_not_unlocked')
    return {
      name: p.name || [p.first_name, p.last_name].filter(Boolean).join(' ') || 'Inconnu',
      title: p.title || '',
      company: p.organization?.name || p.account?.name || '',
      location: [p.city, p.state, p.country].filter(Boolean).join(', '),
      linkedinUrl: p.linkedin_url || '',
      email: locked ? null : rawEmail,
      emailLocked: locked,
    }
  })

  const total = data.pagination?.total_entries ?? leads.length
  return { leads, total }
}
