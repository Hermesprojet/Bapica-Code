import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import {
  ONBOARDING_QUESTIONS,
  enrichClientProfile,
  diagnoseNeeds,
  generateOnboardingReport,
  type EnrichedProfile,
} from '@/lib/client-intelligence'

/**
 * GET /api/client/intelligence — retourne les questions d'onboarding
 */
export async function GET(req: NextRequest) {
  return NextResponse.json({
    steps: ONBOARDING_QUESTIONS,
    total: ONBOARDING_QUESTIONS.length,
    estimatedTime: '3 minutes',
  })
}

/**
 * POST /api/client/intelligence — analyse le profil et génère le diagnostic
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const { userId, answers } = body

    if (!answers || !answers.company_name) {
      return NextResponse.json({ error: 'Profil incomplet' }, { status: 400 })
    }

    // Construire le profil de base
    const baseProfile: EnrichedProfile = {
      companyName: answers.company_name,
      website: answers.website || '',
      sector: answers.sector || 'Autre',
      employees: answers.employee_count || '1',
      revenue: answers.revenue || '< 100K€',
      country: answers.country || 'France',
      city: answers.city || '',
      tvaNumber: answers.tva_number || '',
    }

    const mainProblem = answers.main_problem || ''
    const currentTools = Array.isArray(answers.current_tools) ? answers.current_tools : []
    const growthGoal = answers.growth_goal || ''

    // Phase 2: Enrichissement web
    const profile = await enrichClientProfile(baseProfile)

    // Phase 3: Diagnostic
    const scores = diagnoseNeeds(profile, mainProblem, currentTools, growthGoal)

    // Phase 4: Rapport
    const report = generateOnboardingReport(profile, scores, mainProblem)

    // Sauvegarder dans Supabase si userId fourni
    if (userId) {
      try {
        const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
        const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''
        if (supabaseUrl && supabaseKey) {
          const supabase = createClient(supabaseUrl, supabaseKey)
          await supabase.auth.admin?.updateUserById?.(userId, {
            user_metadata: {
              ...answers,
              profile_enriched: profile,
              agent_scores: scores.slice(0, 3).map(s => ({ id: s.agentId, score: s.score })),
              onboarded_at: new Date().toISOString(),
            },
          })
        }
      } catch {}
    }

    return NextResponse.json({
      success: true,
      profile,
      scores: scores.slice(0, 6),
      topRecommendation: scores[0] || null,
      report,
      nextSteps: scores.slice(0, 3).map((s, i) =>
        `${i + 1}. Commencez avec l'agent **${s.agentName}** (${s.score}/100 de pertinence)`
      ),
    })
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 422 })
  }
}
