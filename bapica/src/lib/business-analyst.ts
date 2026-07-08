/**
 * Business Analyst IA conversationnel
 * Répond aux questions du dirigeant en analysant le profil complet
 */
import Anthropic from '@anthropic-ai/sdk'

export async function analyzeUserQuery(
  query: string,
  profile: any,
  chatHistory: Array<{role: string, content: string}> = []
): Promise<string> {
  const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY || '' })

  const systemPrompt = `Tu es l'analyste business IA de Bapica. Tu as accès au profil complet de l'entreprise et tu réponds aux questions du dirigeant.

Tu es :
- Direct et pragmatique (pas de blabla)
- Concret (des chiffres, des actions, pas de théorie)
- Challengeant (tu dis ce qui ne va pas, pas juste ce qui fait plaisir)
- Contextuel (tu t'adaptes au secteur, à la taille, au stade)

Tu réponds en 3-6 phrases maximum. Tu cites des chiffres du profil quand pertinent.
Tu n'hésites pas à poser une question de clarification si nécessaire.`

  const contextPrompt = `Voici le profil complet de l'entreprise :

🏢 ${profile.companyName || 'Entreprise'}
📊 Secteur : ${profile.sector || 'Non spécifié'}
👥 Taille : ${profile.companySize || 'TPE'} — ${profile.employeeCount || 1} personne(s)
📈 Stade : ${profile.stage || 'early'}
🎯 Maturité digitale : score ${profile.maturityScore || 'N/A'}/100
📋 Priorités : ${(profile.priorities || []).join(', ') || 'Non définies'}
⚠️ Points de douleur : ${(profile.painPoints || []).join(', ') || 'Aucun'}
📣 Acquisition clients : ${(profile.customerAcquisition || []).join(', ') || 'Non spécifié'}
🔧 Outils : ${(profile.currentTools || []).join(', ') || 'Aucun'}
🤖 Agents recommandés : ${(profile.recommendedAgents || []).join(', ')}
💡 Opportunités : ${(profile.growthOpportunities || []).join('; ')}
⚡ Risques : ${(profile.riskFactors || []).map((r: any) => typeof r === 'string' ? r : `${r.risk} (sévérité: ${r.severity}, proba: ${r.probability}%)`).join('; ')}
💰 ROI estimé : ${(profile.roiEstimates || []).map((r: any) => `${r.area}: ${r.costSaved}`).join(', ')}
🏆 Niveau de maturité Bapica : ${profile.maturityLevel || '1'}/5
📊 Position marché : ${profile.marketPosition || 'non définie'}

Question du dirigeant : ${query}

Réponds en t'appuyant sur les données du profil. Sois précis et actionnable.`

  const messages: any[] = [
    ...chatHistory.slice(-6).map(m => ({ role: m.role, content: m.content })),
    { role: 'user', content: contextPrompt },
  ]

  const msg = await anthropic.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 500,
    system: systemPrompt,
    temperature: 0.6,
    messages,
  })

  return (msg.content as any[]).find((b: any) => b.type === 'text')?.text || 'Je n\'ai pas pu analyser cette question.'
}

/**
 * Génère des insights proactifs personnalisés
 */
export async function generateInsights(profile: any): Promise<string[]> {
  const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY || '' })

  const prompt = `Génère 3 insights stratégiques ACTIONABLES pour cette entreprise :

🏢 ${profile.companyName || 'Entreprise'} — Secteur : ${profile.sector}
👥 ${profile.employeeCount || 1} personne(s) — stade ${profile.stage || 'early'}
🎯 Maturité : ${profile.maturityScore || 'N/A'}/100

Règles :
- Chaque insight = une phrase actionable
- Spécifique au secteur et au stade
- Priorisé par impact
- Format : UNIQUEMENT les 3 phrases, séparées par |

Réponds uniquement avec les 3 insights.`

  const msg = await anthropic.messages.create({
    model: 'claude-haiku-4-5',
    max_tokens: 300,
    temperature: 0.7,
    messages: [{ role: 'user', content: prompt }],
  })

  const text = (msg.content as any[]).find((b: any) => b.type === 'text')?.text || ''
  return text.split('|').map((s: string) => s.trim()).filter(Boolean).slice(0, 3)
}
