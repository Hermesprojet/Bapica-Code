import { NextRequest, NextResponse } from 'next/server'
import {
  autoConfigure,
  predictFuture,
  detectWorkflows,
  orchestrationScore,
} from '@/lib/bapica-genesis'

export async function GET(req: NextRequest) {
  const params = req.nextUrl.searchParams
  const mode = params.get('mode') || 'all'

  // Profil mock pour démo (en prod: depuis Supabase)
  const profile = {
    sector: params.get('sector') || 'Services B2B',
    employees: params.get('employees') || '10',
    revenue: params.get('revenue') || '500K€ - 2M€',
    country: params.get('country') || 'France',
    website: params.get('website') || '',
    tools: (params.get('tools') || 'gmail,notion').split(','),
    websiteHasLegalPages: params.get('legal') === 'true',
  }

  const results: any = {}

  if (mode === 'config' || mode === 'all') {
    results.config = autoConfigure(profile)
  }

  if (mode === 'predict' || mode === 'all') {
    results.predictions = predictFuture(profile, [])
  }

  if (mode === 'workflow' || mode === 'all') {
    const connected = profile.tools
    results.workflows = detectWorkflows(connected)
    results.orchestration = orchestrationScore(results.workflows)
  }

  return NextResponse.json(results)
}

/**
 * POST /api/genesis/start — Lance Genesis
 * Auto-configure + prédictions + workflows en une fois
 */
export async function POST(req: NextRequest) {
  try {
    const { profile } = await req.json()

    const config = autoConfigure(profile || {})
    const predictions = predictFuture(profile || {}, [])
    const connected = profile?.tools || []
    const workflows = detectWorkflows(connected)
    const score = orchestrationScore(workflows)

    return NextResponse.json({
      genesis: true,
      config,
      predictions: predictions.slice(0, 5),
      workflows,
      orchestration: score,
      summary: [
        `🤖 ${config.activatedAgents.length} agents activés automatiquement`,
        `🔮 ${predictions.length} prédictions générées`,
        `🔄 ${workflows.length} workflows détectés`,
        `⚡ ${score.potential} d'économies potentielles par mois`,
      ].join('\n'),
    })
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 422 })
  }
}
