import { NextRequest, NextResponse } from 'next/server'
import { analyzeUserQuery } from '@/lib/business-analyst'

const corsHeaders = () => ({
  'Access-Control-Allow-Origin': 'https://bapica.com',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
})

export async function OPTIONS() {
  return NextResponse.json({}, { headers: corsHeaders() })
}

// POST /api/business-chat
// Chat conversationnel avec l'analyste business IA
export async function POST(req: NextRequest) {
  try {
    const { query, profile, history } = await req.json()
    
    if (!query || !profile) {
      return NextResponse.json({ error: 'query et profile requis' }, { status: 400, headers: corsHeaders() })
    }

    const response = await analyzeUserQuery(query, profile, history || [])
    return NextResponse.json({ response }, { headers: corsHeaders() })

  } catch (error) {
    console.error('Business chat error:', error)
    return NextResponse.json(
      { error: 'Analyse indisponible' },
      { status: 500, headers: corsHeaders() }
    )
  }
}
