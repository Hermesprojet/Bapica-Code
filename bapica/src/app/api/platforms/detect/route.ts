import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { detectPlatformsFromProfile, classifyEcosystem, generateIntegrationSuggestions, getPlatformCategories } from '@/lib/platform-detector'

export async function GET(req: NextRequest) {
  const authHeader = req.headers.get('authorization')
  if (!authHeader) {
    return NextResponse.json({ error: 'Non authentifié' }, { status: 401 })
  }

  const token = authHeader.replace('Bearer ', '')
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''

  if (!supabaseUrl || !supabaseKey) {
    return NextResponse.json({ error: 'Configuration Supabase manquante' }, { status: 500 })
  }

  const supabase = createClient(supabaseUrl, supabaseKey)
  const { data: { user }, error } = await supabase.auth.getUser(token)

  if (error || !user) {
    return NextResponse.json({ error: 'Token invalide' }, { status: 401 })
  }

  const profile = {
    email: user.email || '',
    companyName: user.user_metadata?.company_name || '',
    sector: user.user_metadata?.sector || '',
    employeeCount: user.user_metadata?.employee_count || 0,
    hasWebsite: !!user.user_metadata?.website,
  }

  const detected = detectPlatformsFromProfile(profile)
  const ecosystem = classifyEcosystem(detected)
  const suggestions = generateIntegrationSuggestions(ecosystem)

  // Récupérer les intégrations déjà connectées
  const { data: connected } = await supabase
    .from('integrations')
    .select('provider')
    .eq('user_id', user.id)

  const connectedProviders = new Set((connected || []).map((c: any) => c.provider))

  // Filtrer: ne pas suggérer ce qui est déjà connecté
  const available = detected.filter(d => !connectedProviders.has(d.provider))

  return NextResponse.json({
    detected: available,
    connected: connectedProviders.size > 0 ? [...connectedProviders] : [],
    ecosystem,
    suggestions,
    categories: getPlatformCategories(),
    stats: {
      total: available.length,
      highConfidence: available.filter(d => d.confidence === 'high').length,
      readyToConnect: available.filter(d => d.readyToConnect).length,
    },
  })
}
