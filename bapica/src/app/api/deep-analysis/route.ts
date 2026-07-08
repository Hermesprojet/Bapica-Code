import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { analyzeBusinessProfile } from '@/lib/business-profile'
import { generateDeepAnalysis, type DeepAnalysis } from '@/lib/deep-analysis'
import { buildClientMemory } from '@/lib/client-memory'

const corsHeaders = () => ({
  'Access-Control-Allow-Origin': 'https://bapica.com',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
})

export async function OPTIONS() {
  return NextResponse.json({}, { headers: corsHeaders() })
}

// GET /api/deep-analysis
// Analyse profonde combinant toutes les sources d'intelligence
export async function GET(req: NextRequest) {
  try {
    // Auth
    const supabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL || '',
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''
    )
    const { data: { user }, error: authError } = await supabase.auth.getUser()
    if (authError || !user) {
      return NextResponse.json({ error: 'Non authentifié' }, { status: 401, headers: corsHeaders() })
    }

    // Charger le profil
    const { data: profile } = await supabase
      .from('profiles')
      .select('*')
      .eq('id', user.id)
      .single()

    const onboarding = profile?.onboarding_data || user.user_metadata?.onboarding_data || {}
    const businessProfile = analyzeBusinessProfile(onboarding)
    const memory = buildClientMemory(onboarding, profile?.conversation_history || [])

    // Analyse profonde
    const analysis = generateDeepAnalysis(businessProfile, memory)

    return NextResponse.json(analysis, { headers: corsHeaders() })
  } catch (error) {
    return NextResponse.json(
      { error: 'Analyse indisponible' },
      { status: 500, headers: corsHeaders() }
    )
  }
}
