import { NextRequest, NextResponse } from 'next/server'
import { generateCompetitiveAnalysis, identifyOpportunities, getCompetitiveIntel, getSectorTrends } from '@/lib/market-intelligence'

const corsHeaders = () => ({
  'Access-Control-Allow-Origin': 'https://bapica.com',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
})

export async function OPTIONS() {
  return NextResponse.json({}, { headers: corsHeaders() })
}

// GET /api/market-intelligence?sector=ecommerce
export async function GET(req: NextRequest) {
  try {
    const url = new URL(req.url)
    const sector = url.searchParams.get('sector') || 'services'
    const type = url.searchParams.get('type') || 'all'

    const data: any = {}

    if (type === 'all' || type === 'competitive') {
      data.competitiveAnalysis = generateCompetitiveAnalysis(sector)
    }
    if (type === 'all' || type === 'opportunities') {
      data.opportunities = identifyOpportunities(sector, {})
    }
    if (type === 'all' || type === 'intel') {
      data.competitiveIntel = getCompetitiveIntel()
    }
    if (type === 'all' || type === 'trends') {
      data.trends = getSectorTrends(sector)
    }

    return NextResponse.json(data, { headers: corsHeaders() })
  } catch (error) {
    return NextResponse.json({ error: 'Analyse indisponible' }, { status: 500, headers: corsHeaders() })
  }
}
