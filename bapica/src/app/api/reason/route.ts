import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { analyzeBusinessProfile } from '@/lib/business-profile'
import { buildClientMemory } from '@/lib/client-memory'
import { think } from '@/lib/reasoning-engine'

const corsHeaders = () => ({
  'Access-Control-Allow-Origin': 'https://bapica.com',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
})

export async function OPTIONS() {
  return NextResponse.json({}, { headers: corsHeaders() })
}

// GET /api/reason
// Fait raisonner Bapica sur une question business
export async function GET(req: NextRequest) {
  try {
    const supabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL || '',
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''
    )
    const { data: { user }, error } = await supabase.auth.getUser()
    if (error || !user) {
      return NextResponse.json({ error: 'Non authentifié' }, { status: 401, headers: corsHeaders() })
    }

    const { data: profile } = await supabase
      .from('profiles')
      .select('*')
      .eq('id', user.id)
      .single()

    const onboarding = profile?.onboarding_data || user.user_metadata?.onboarding_data || {}
    const businessProfile = analyzeBusinessProfile(onboarding)
    const memory = buildClientMemory(onboarding, profile?.conversation_history || [])

    const question = new URL(req.url).searchParams.get('q') || undefined
    const result = think(businessProfile, memory, question)

    return NextResponse.json(result, { headers: corsHeaders() })
  } catch (error) {
    return NextResponse.json({ error: 'Raisonnement indisponible' }, { status: 500, headers: corsHeaders() })
  }
}
