import { NextRequest, NextResponse } from 'next/server'
import Anthropic from '@anthropic-ai/sdk'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { isAdminEmail } from '@/lib/admin'
import { listSignals } from '@/lib/insights/store'

/**
 * GET /api/insights — rapport d'apprentissage produit (ADMIN uniquement).
 * Agrège les signaux clients récents et demande à Claude un rapport structuré :
 * thèmes, fréquence, exemples, et améliorations proposées priorisées (impact/effort).
 */
export async function GET(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  if (!isAdminEmail(user.email)) {
    return NextResponse.json({ error: 'Réservé à l’administrateur.' }, { status: 403 })
  }

  let signals
  try {
    signals = await listSignals(300)
  } catch (e) {
    if (String(e).includes('SIGNALS_TABLE_MISSING')) {
      return NextResponse.json({ error: 'Base non initialisée : exécutez supabase-schema.sql.', needsSetup: true }, { status: 400 })
    }
    return NextResponse.json({ error: 'Lecture des signaux impossible.' }, { status: 500 })
  }

  if (!signals.length) {
    return NextResponse.json({ report: null, count: 0, message: 'Pas encore de signaux clients à analyser.' })
  }

  const apiKey = process.env.ANTHROPIC_API_KEY
  if (!apiKey) return NextResponse.json({ error: 'Analyse indisponible (clé API).' }, { status: 503 })

  // Compacte les signaux pour le prompt.
  const lines = signals.map((s) => {
    const flags = [s.type, (s.meta as any)?.unanswered ? 'sans-réponse' : '', (s.meta as any)?.visitor ? 'visiteur' : ''].filter(Boolean).join('/')
    return `- [${flags}] ${s.content.slice(0, 200)}`
  }).join('\n').slice(0, 12000)

  const system = `Tu es analyste produit pour Bapica (plateforme SaaS multi-agents IA pour PME).
On te donne des SIGNAUX bruts d'expérience client : questions posées au chatbot d'aide, feedback,
échecs d'actions. Produis un rapport EXPLOITABLE, en français, au format JSON STRICT :
{
  "resume": "2-3 phrases de synthèse",
  "themes": [
    {
      "titre": "libellé court du thème",
      "frequence": nombre_de_signaux_concernes,
      "constat": "ce que ça révèle (1-2 phrases)",
      "exemples": ["citation courte", "citation courte"],
      "propositions": [
        { "action": "amélioration concrète et réalisable", "impact": "faible|moyen|fort", "effort": "faible|moyen|fort" }
      ]
    }
  ]
}
Règles : regroupe les signaux similaires, classe les thèmes du plus fréquent au moins fréquent,
propose des améliorations CONCRÈTES (pas de généralités), 3 à 6 thèmes maximum. Réponds UNIQUEMENT
avec le JSON, sans texte autour.`

  try {
    const client = new Anthropic({ apiKey, timeout: 40000 })
    const completion = await client.messages.create({
      model: 'claude-sonnet-4-5',
      max_tokens: 2000,
      temperature: 0.2,
      system,
      messages: [{ role: 'user', content: `Voici ${signals.length} signaux récents :\n${lines}` }],
    })
    const raw = completion.content.filter((b): b is Anthropic.TextBlock => b.type === 'text').map((b) => b.text).join('\n').trim()
    const jsonStr = raw.replace(/^```json\s*/i, '').replace(/```$/i, '').trim()
    let report: unknown = null
    try { report = JSON.parse(jsonStr) } catch { return NextResponse.json({ error: 'Rapport illisible, réessayez.' }, { status: 502 }) }
    return NextResponse.json({ report, count: signals.length })
  } catch (e) {
    return NextResponse.json({ error: `Analyse impossible : ${String(e instanceof Error ? e.message : e)}` }, { status: 502 })
  }
}
