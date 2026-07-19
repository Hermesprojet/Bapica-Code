import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { searchLeads, isApolloConfigured } from '@/lib/apollo'

/**
 * POST /api/leads/search — recherche de prospects B2B via Apollo.
 * Auth : Bearer Supabase. Corps : { titles, locations, keywords, employeeRanges, page }.
 */
export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) {
    return NextResponse.json({ error: 'Non authentifié' }, { status: 401 })
  }

  if (!isApolloConfigured()) {
    return NextResponse.json(
      { error: 'Configuration Apollo manquante. Ajoutez APOLLO_API_KEY dans Vercel puis redéployez.' },
      { status: 400 }
    )
  }

  try {
    const { titles, locations, keywords, employeeRanges, page } = await req.json()
    const result = await searchLeads({
      titles: toArr(titles),
      locations: toArr(locations),
      keywords: typeof keywords === 'string' && keywords.trim() ? keywords.trim() : undefined,
      employeeRanges: toArr(employeeRanges),
      page: Number(page) || 1,
      perPage: 10,
    })
    return NextResponse.json({ success: true, ...result })
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e)
    if (msg.includes('APOLLO_NOT_CONFIGURED')) {
      return NextResponse.json({ error: 'Configuration Apollo manquante.' }, { status: 400 })
    }
    if (msg.includes('APOLLO_PLAN_REQUIRED')) {
      return NextResponse.json(
        { error: "Votre plan Apollo ne permet pas l'accès API (People Search nécessite un plan Apollo payant). Passez à un plan payant sur app.apollo.io, ou choisissez une autre source de leads." },
        { status: 402 }
      )
    }
    if (msg.includes('APOLLO_UNAUTHORIZED')) {
      return NextResponse.json({ error: 'Clé Apollo invalide. Vérifiez APOLLO_API_KEY dans Vercel.' }, { status: 401 })
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
