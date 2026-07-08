import { NextRequest, NextResponse } from 'next/server'
import Anthropic from '@anthropic-ai/sdk'

const corsHeaders = () => ({
  'Access-Control-Allow-Origin': 'https://bapica.com',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
})

export async function OPTIONS() {
  return NextResponse.json({}, { headers: corsHeaders() })
}

// POST /api/business-analysis
// Analyse stratégique IA d'un profil business
export async function POST(req: NextRequest) {
  try {
    const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY || '' })
    const { profile } = await req.json()

    if (!profile) {
      return NextResponse.json({ error: 'Profil requis' }, { status: 400, headers: corsHeaders() })
    }

    const systemPrompt = `Tu es un expert en stratégie d'entreprise spécialisé dans l'analyse de PME.
Tu analyses des profils d'entreprise et produis des recommandations stratégiques actionnables, concrètes, et spécifiques au contexte.
Tu parles français. Tu es direct, pragmatique, et tu ne fais pas de théorie vague.
Tu réponds TOUJOURS en JSON valide avec ces champs :
{
  "strategicMemo": "Analyse stratégique en 2-3 phrases",
  "keyInsight": "L'insight le plus important",
  "growthForecast": "Prévision de croissance à 12 mois avec Bapica",
  "top3Recommendations": ["reco1", "reco2", "reco3"],
  "healthScore": 75
}`

    const userPrompt = `Analyse ce profil d'entreprise et donne des recommandations stratégiques :

Entreprise : ${profile.companyName || 'Non spécifié'}
Secteur : ${profile.sector || 'Non spécifié'}
Taille : ${profile.companySize || 'TPE'}
Effectif : ${profile.employeeCount || 1} personne(s)
Stade : ${profile.stage || 'early'}
Maturité digitale : ${profile.digitalMaturity || 'medium'}
Priorités : ${(profile.priorities || []).join(', ') || 'Non définies'}
Points de douleur : ${(profile.painPoints || []).join(', ') || 'Aucun'}
Acquisition clients : ${(profile.customerAcquisition || []).join(', ') || 'Non spécifié'}
Outils : ${(profile.currentTools || []).join(', ') || 'Aucun'}
Agents recommandés : ${(profile.recommendedAgents || []).join(', ')}
Problèmes : ${(profile.riskFactors || []).map((r: any) => typeof r === 'string' ? r : r.risk).join('; ') || 'Aucun'}`

    const msg = await anthropic.messages.create({
      model: 'claude-sonnet-4-6',
      max_tokens: 600,
      system: systemPrompt,
      temperature: 0.4,
      messages: [{ role: 'user', content: userPrompt }],
    })

    const text = msg.content.find((b: any) => b.type === 'text')?.text || ''
    
    // Extraire le JSON
    const jsonMatch = text.match(/\{[\s\S]*\}/)
    if (!jsonMatch) {
      return NextResponse.json({ 
        strategicMemo: text.trim(),
        healthScore: 60,
        top3Recommendations: ['Analyser plus en détail', 'Activer les agents recommandés', 'Suivre le plan d\'action'],
        keyInsight: 'Analyse en cours',
        growthForecast: 'Potentiel de croissance significatif avec automatisation',
      }, { headers: corsHeaders() })
    }

    const analysis = JSON.parse(jsonMatch[0])
    return NextResponse.json(analysis, { headers: corsHeaders() })

  } catch (error) {
    console.error('Business analysis error:', error)
    return NextResponse.json(
      { error: 'Analyse temporairement indisponible' },
      { status: 500, headers: corsHeaders() }
    )
  }
}
