import { NextRequest, NextResponse } from 'next/server'
import {
  generatePredictiveAlerts,
  orchestrateGoal,
  selectOptimalModel,
  calculateROI,
  simulateScenario,
  parseVoiceIntent,
  applyFeedback,
  buildMemoryPrompt,
  type ModelDecision,
  type ROIMetrics,
  type PredictiveAlert,
  type FeedbackSignal,
} from '@/lib/bapica-cortex'

/**
 * GET /api/cortex — Tableau de bord intelligent
 * Retourne tout : alerts, ROI, modèles actifs
 */
export async function GET(req: NextRequest) {
  const userId = req.headers.get('x-user-id') || 'demo'
  const params = req.nextUrl.searchParams
  const mode = params.get('mode') || 'dashboard'

  const mockProfile = {
    companyName: 'Démo',
    revenue: '500K€ - 2M€',
    employee_count: '6-15',
    sector: 'Services B2B',
    websiteHasLegalPages: false,
  }

  const alerts = generatePredictiveAlerts(mockProfile, {
    lastLogin: new Date().toISOString(),
    messagesCount: 45,
  })

  const roi = calculateROI({
    messagesCount: 45,
    agentsUsed: ['prospection-strategie', 'support', 'accounting'],
    problemsResolved: 8,
    profile: mockProfile,
  })

  return NextResponse.json({
    mode,
    alerts: alerts.slice(0, 5),
    roi,
    summary: `Bapica vous a fait économiser ${Math.round(roi.timeSavedMinutes / 60)}h ce mois (≈${roi.moneyEquivalent}€)`,
  })
}

/**
 * POST /api/cortex — Actions intelligentes
 * action=autopilot | simulate | voice | feedback | model-select
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const { action, ...params } = body

    switch (action) {
      case 'autopilot': {
        const goal = orchestrateGoal(params.goal || '', params.profile || {})
        return NextResponse.json({ success: true, goal })
      }

      case 'simulate': {
        const result = simulateScenario({
          scenario: params.scenario || '',
          currentMetrics: params.metrics || { revenue: 1000000, employees: 10, margin: 30, clients: 50, avgPrice: 5000 },
        })
        return NextResponse.json({ success: true, result })
      }

      case 'voice': {
        const command = parseVoiceIntent(params.transcript || '')
        return NextResponse.json({ success: true, command })
      }

      case 'feedback': {
        applyFeedback(params as FeedbackSignal)
        return NextResponse.json({ success: true, message: 'Feedback enregistré' })
      }

      case 'model-select': {
        const decision = selectOptimalModel(
          params.message || '',
          params.agentId || 'general',
          params.historyLength || 0
        )
        return NextResponse.json({ success: true, decision })
      }

      case 'memory': {
        const memory = buildMemoryPrompt(params.memories || [])
        return NextResponse.json({ success: true, memoryPrompt: memory })
      }

      default:
        return NextResponse.json({ error: 'Action inconnue' }, { status: 400 })
    }
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 422 })
  }
}
