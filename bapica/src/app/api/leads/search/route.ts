import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { searchLeads, isApolloConfigured } from '@/lib/apollo'
import { domainSearch, cleanDomain, isHunterConfigured } from '@/lib/hunter'

/**
 * POST /api/leads/search — recherche de prospects B2B.
 * Auth : Bearer Supabase.
 * - source 'apollo' (défaut) : { titles, locations, keywords, employeeRanges, page } (découverte).
 * - source 'hunter' : { domain } (personnes + emails d'un domaine d'entreprise).
 */
export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) {
    return NextResponse.json({ error: 'Non authentifié' }, { status: 401 })
  }

  let payload: any = {}
  try {
    payload = await req.json()
  } catch {
    return NextResponse.json({ error: 'Requête invalide.' }, { status: 400 })
  }
  const source = payload.source === 'hunter' ? 'hunter' : 'apollo'

  try {
    if (source === 'hunter') {
      if (!isHunterConfigured()) {
        return NextResponse.json(
          { error: 'Configuration Hunter manquante. Ajoutez HUNTER_API_KEY dans Vercel puis redéployez.' },
          { status: 400 }
        )
      }
      const domain = typeof payload.domain === 'string' ? cleanDomain(payload.domain) : ''
      if (!domain) {
        return NextResponse.json({ error: "Renseignez le domaine de l'entreprise (ex : exemple.com)." }, { status: 400 })
      }
      const result = await domainSearch(domain, 10)
      return NextResponse.json({ success: true, source, ...result })
    }

    // source === 'apollo'
    if (!isApolloConfigured()) {
      return NextResponse.json(
        { error: 'Configuration Apollo manquante. Ajoutez APOLLO_API_KEY dans Vercel puis redéployez.' },
        { status: 400 }
      )
    }
    const result = await searchLeads({
      titles: toArr(payload.titles),
      locations: toArr(payload.locations),
      keywords: typeof payload.keywords === 'string' && payload.keywords.trim() ? payload.keywords.trim() : undefined,
      employeeRanges: toArr(payload.employeeRanges),
      page: Number(payload.page) || 1,
      perPage: 10,
    })
    return NextResponse.json({ success: true, source, ...result })
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e)
    if (msg.includes('APOLLO_NOT_CONFIGURED')) {
      return NextResponse.json({ error: 'Configuration Apollo manquante.' }, { status: 400 })
    }
    if (msg.includes('APOLLO_PLAN_REQUIRED')) {
      return NextResponse.json(
        { error: "Votre plan Apollo ne permet pas l'accès API (People Search nécessite un plan Apollo payant). Passez à un plan payant sur app.apollo.io, ou utilisez la source Hunter." },
        { status: 402 }
      )
    }
    if (msg.includes('APOLLO_UNAUTHORIZED')) {
      return NextResponse.json({ error: 'Clé Apollo invalide. Vérifiez APOLLO_API_KEY dans Vercel.' }, { status: 401 })
    }
    if (msg.includes('HUNTER_UNAUTHORIZED')) {
      return NextResponse.json({ error: 'Clé Hunter invalide. Vérifiez HUNTER_API_KEY dans Vercel.' }, { status: 401 })
    }
    if (msg.includes('HUNTER_RATE_LIMIT')) {
      return NextResponse.json({ error: 'Quota Hunter atteint (limite du plan). Réessayez plus tard ou passez à un plan supérieur.' }, { status: 429 })
    }
    return NextResponse.json({ error: `Échec de la recherche : ${msg}` }, { status: 502 })
  }
}

function toArr(v: unknown): string[] | undefined {
  if (Array.isArray(v)) {
    const arr = v.filter((x) => typeof x === 'string' && x.trim()).map((x) => (x as string).trim())
    return arr.length ? arr : undefined
  }
  if (typeof v === 'string' && v.trim()) {
    const arr = v.split(',').map((s) => s.trim()).filter(Boolean)
    return arr.length ? arr : undefined
  }
  return undefined
}
