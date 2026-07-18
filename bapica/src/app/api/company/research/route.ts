import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { researchCompany } from '@/lib/company-research'
import { ingestClientDocument } from '@/lib/client-knowledge'

export const dynamic = 'force-dynamic'
export const maxDuration = 60

/**
 * POST /api/company/research
 * Recherche internet sur l'entreprise du client (site + web) → résumé Claude →
 * stocké comme document de connaissance (utilisable par les agents via le RAG).
 */
export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non authentifié.' }, { status: 401 })

  const o = (user.user_metadata as any)?.onboarding_data || {}
  const companyName = (o.companyName || '').toString().trim()
  if (!companyName) {
    return NextResponse.json({ error: "Renseignez d'abord le nom de votre société (profil d'onboarding)." }, { status: 400 })
  }

  if (!process.env.ANTHROPIC_API_KEY) {
    return NextResponse.json({ error: 'Recherche en cours de configuration (clé API).' }, { status: 503 })
  }

  try {
    const { summary, sources } = await researchCompany({
      companyName,
      website: o.website,
      sector: o.sector?.trim() || o.activityOther?.trim() || o.activity,
      city: o.city,
      country: o.country,
    })

    if (!summary) {
      return NextResponse.json({ error: 'Aucun résumé exploitable.' }, { status: 422 })
    }

    // On stocke dans la base de connaissances du client (si OpenAI configuré).
    let stored = false
    if (process.env.OPENAI_API_KEY) {
      try {
        const doc = `Profil de ${companyName} (recherche web) :\n\n${summary}\n\nSources : ${sources.join(', ')}`
        const { inserted } = await ingestClientDocument(user.id, `Recherche web — ${companyName}`, doc)
        stored = inserted > 0
      } catch { /* stockage optionnel */ }
    }

    return NextResponse.json({ success: true, summary, sources, stored })
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : String(e) }, { status: 502 })
  }
}
