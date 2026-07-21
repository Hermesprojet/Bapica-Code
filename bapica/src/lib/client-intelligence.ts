/**
 * Bapica Client Intelligence Engine
 * 
 * Connaît chaque client en profondeur :
 * Phase 1 - Onboarding intelligent (questionnaire)
 * Phase 2 - Enrichissement web automatique
 * Phase 3 - Diagnostic automatique des besoins
 * Phase 4 - Rapport personnalisé
 */

// ─── PHASE 1: QUESTIONNAIRE ───────────────────────────────

export interface OnboardingStep {
  id: string
  question: string
  type: 'text' | 'number' | 'select' | 'url' | 'multi' | 'open'
  options?: string[]
  placeholder?: string
  required: boolean
  why: string
  scoring?: Record<string, Record<string, number>>
}

export const ONBOARDING_QUESTIONS: OnboardingStep[] = [
  {
    id: 'company_name',
    question: 'Quel est le nom de votre société ?',
    type: 'text',
    placeholder: 'Ex: SARL Dubois Électricité',
    required: true,
    why: 'Identité légale + recherche d\'informations publiques',
  },
  {
    id: 'website',
    question: 'Quel est votre site web ?',
    type: 'url',
    placeholder: 'https://www.monentreprise.com',
    required: false,
    why: 'Source d\'information la plus riche pour analyser votre activité',
  },
  {
    id: 'sector',
    question: 'Quel est votre secteur d\'activité ?',
    type: 'select',
    options: ['Restauration', 'Commerce / Retail', 'Services B2B', 'E-commerce', 'BTP / Artisanat', 'SaaS / Tech', 'Santé / Médical', 'Industrie', 'Conseil / Freelance', 'Autre'],
    required: true,
    why: 'Active les connaissances sectorielles et les benchmarks',
  },
  {
    id: 'employee_count',
    question: 'Combien de personnes travaillent dans votre entreprise ?',
    type: 'select',
    options: ['1 (solo)', '2-5', '6-15', '16-50', '51-200', '200+'],
    required: true,
    why: 'La taille détermine les besoins en RH, outils, et complexité',
  },
  {
    id: 'revenue',
    question: 'Quel était votre chiffre d\'affaires l\'an dernier ?',
    type: 'select',
    options: ['< 100K€', '100K€ - 500K€', '500K€ - 2M€', '2M€ - 10M€', '> 10M€'],
    required: true,
    why: 'Capacité financière + adaptation du pricing et des conseils',
  },
  {
    id: 'country',
    question: 'Dans quel pays êtes-vous basé ?',
    type: 'select',
    options: ['France', 'Belgique', 'Espagne', 'Italie', 'Allemagne', 'Pologne', 'Suisse', 'Autre'],
    required: true,
    why: 'Contexte réglementaire, TVA, culture business',
  },
  {
    id: 'city',
    question: 'Dans quelle ville ?',
    type: 'text',
    placeholder: 'Ex: Lyon',
    required: false,
    why: 'Concurrence locale + Google Places',
  },
  {
    id: 'main_problem',
    question: 'Quel est votre PLUS GROS défi en ce moment ?',
    type: 'open',
    placeholder: 'Décrivez en une phrase ce qui vous empêche de dormir...',
    required: true,
    why: 'Identifie le besoin PRIORITAIRE',
    scoring: {
      accounting: { 'trésorerie': 30, 'facture': 30, 'compta': 30, 'tva': 25, 'fiscal': 25 },
      support: { 'client mécontent': 25, 'sav': 25, 'support': 30, 'plainte': 25 },
      recruiter: { 'recruter': 30, 'embaucher': 30, 'trouver': 20, 'candidat': 25 },
      'prospection-strategie': { 'client': 25, 'prospect': 30, 'vente': 25, 'ca': 20, 'chiffre': 20 },
      legal: { 'juridique': 30, 'contrat': 25, 'rgpd': 25, 'conformité': 25 },
    },
  },
  {
    id: 'current_tools',
    question: 'Quels outils utilisez-vous actuellement ?',
    type: 'multi',
    options: ['Excel / Papier', 'QuickBooks', 'Pennylane', 'Sage', 'HubSpot', 'Salesforce', 'Slack', 'Teams', 'Gmail', 'Outlook', 'Notion', 'Trello', 'Shopify', 'WooCommerce', 'Stripe', 'PayPal', 'Aucun outil pro'],
    required: false,
    why: 'Détection de la maturité digitale et des intégrations possibles',
  },
  {
    id: 'growth_goal',
    question: 'Quel est votre objectif principal avec Bapica ?',
    type: 'select',
    options: ['Augmenter mon CA', 'Gagner du temps', 'Mieux gérer mes clients', 'Automatiser la compta', 'Trouver des clients', 'Recruter', 'Tout ça !'],
    required: true,
    why: 'Aligne les agents recommandés avec l\'objectif',
  },
  {
    id: 'tva_number',
    question: 'Numéro de TVA intracommunautaire (optionnel)',
    type: 'text',
    placeholder: 'FR12345678901',
    required: false,
    why: 'Vérification automatique + conformité facturation',
  },
]

// ─── PHASE 2: ENRICHISSEMENT WEB ──────────────────────────

export interface EnrichedProfile {
  companyName: string
  website?: string
  sector: string
  employees: string
  revenue: string
  country: string
  city?: string
  tvaNumber?: string
  // Données enrichies automatiquement
  googleRating?: number
  googleReviews?: number
  linkedinEmployees?: number
  linkedinJobs?: number
  websiteSpeed?: number
  websiteMobile?: boolean
  websiteHasBlog?: boolean
  websiteHasLegalPages?: boolean
  socialActivity?: { platform: string; posts: number; followers: number }[]
  legalStatus?: string
  foundedYear?: number
  estimatedTraffic?: number
}

/**
 * Enrichit le profil client avec des données web
 */
export async function enrichClientProfile(base: Partial<EnrichedProfile>): Promise<EnrichedProfile> {
  const profile: EnrichedProfile = { ...base } as EnrichedProfile
  const website = base.website

  if (website) {
    try {
      // Analyser le site web
      const siteData = await analyzeWebsite(website)
      profile.websiteSpeed = siteData.speed
      profile.websiteMobile = siteData.mobile
      profile.websiteHasBlog = siteData.hasBlog
      profile.websiteHasLegalPages = siteData.hasLegalPages
      profile.estimatedTraffic = siteData.traffic
    } catch {}
  }

  if (base.companyName && base.city) {
    try {
      const placesData = await searchGooglePlaces(base.companyName, base.city)
      profile.googleRating = placesData.rating
      profile.googleReviews = placesData.reviews
    } catch {}
  }

  return profile
}

async function analyzeWebsite(url: string) {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(5000) })
    const html = await res.text()
    return {
      speed: estimateSpeed(html),
      mobile: html.includes('viewport'),
      hasBlog: /blog|actualités|news|articles/i.test(html),
      hasLegalPages: /mentions.légales|cgv|politique.confidentialité|rgpd/i.test(html),
      traffic: 0,
    }
  } catch {
    return { speed: 0, mobile: false, hasBlog: false, hasLegalPages: false, traffic: 0 }
  }
}

function estimateSpeed(html: string): number {
  const size = html.length
  if (size < 50000) return 90
  if (size < 150000) return 70
  if (size < 500000) return 50
  return 30
}

async function searchGooglePlaces(name: string, city: string) {
  const key = process.env.GOOGLE_PLACES_API_KEY
  if (!key) return { rating: 0, reviews: 0 }
  try {
    const q = encodeURIComponent(`${name} ${city}`)
    const res = await fetch(`https://maps.googleapis.com/maps/api/place/textsearch/json?query=${q}&key=${key}`)
    const data = await res.json()
    const place = data.results?.[0]
    return { rating: place?.rating || 0, reviews: place?.user_ratings_total || 0 }
  } catch {
    return { rating: 0, reviews: 0 }
  }
}

// ─── PHASE 3: DIAGNOSTIC AUTOMATIQUE ──────────────────────

export interface AgentScore {
  agentId: string
  agentName: string
  score: number
  reasons: string[]
}

/**
 * Score chaque agent sur 100 selon le profil client
 */
export function diagnoseNeeds(profile: EnrichedProfile, mainProblem: string, currentTools: string[], growthGoal: string): AgentScore[] {
  const scores: AgentScore[] = []
  const problem = mainProblem.toLowerCase()
  const tools = currentTools.join(' ').toLowerCase()

  // 1. Comptabilité
  let accountingScore = 0
  const accountingReasons: string[] = []
  if (tools.includes('excel') || tools.includes('papier') || tools.includes('aucun')) { accountingScore += 40; accountingReasons.push('Pas d\'outil compta pro') }
  if (profile.revenue.includes('500K') || profile.revenue.includes('2M') || profile.revenue.includes('10M')) { accountingScore += 15; accountingReasons.push('Volume financier significatif') }
  if (problem.match(/trésorerie|facture|compta|tva|fiscal/)) { accountingScore += 25; accountingReasons.push('Défi comptable déclaré') }
  scores.push({ agentId: 'accounting', agentName: 'Comptable', score: Math.min(accountingScore, 100), reasons: accountingReasons })

  // 2. Recrutement
  let recruiterScore = 0
  const recruiterReasons: string[] = []
  if (profile.employees === '6-15' || profile.employees === '16-50') { recruiterScore += 20; recruiterReasons.push('Taille propice au recrutement') }
  if (problem.match(/recruter|embaucher|candidat|trouver/)) { recruiterScore += 30; recruiterReasons.push('Défi recrutement déclaré') }
  if ((profile as any).linkedinJobs && (profile as any).linkedinJobs > 3) { recruiterScore += 25; recruiterReasons.push('Recrutement actif détecté') }
  scores.push({ agentId: 'recruiter', agentName: 'Recruteur', score: Math.min(recruiterScore, 100), reasons: recruiterReasons })

  // 3. Prospection / Croissance
  let growthScore = 0
  const growthReasons: string[] = []
  if (growthGoal.includes('CA') || growthGoal.includes('client')) { growthScore += 30; growthReasons.push('Objectif croissance') }
  if (problem.match(/client|prospect|vente|ca|chiffre/)) { growthScore += 25; growthReasons.push('Défi commercial déclaré') }
  if (profile.revenue.includes('100K') || profile.revenue.includes('<')) { growthScore += 15; growthReasons.push('Petite structure → besoin prospection') }
  if (!profile.websiteHasBlog) { growthScore += 10; growthReasons.push('Pas de contenu marketing') }
  scores.push({ agentId: 'prospection-strategie', agentName: 'Conseiller Croissance', score: Math.min(growthScore, 100), reasons: growthReasons })

  // 4. Support
  let supportScore = 0
  const supportReasons: string[] = []
  if (problem.match(/client mécontent|sav|support|plainte|mécontent/)) { supportScore += 30; supportReasons.push('Défi support déclaré') }
  if ((profile.googleRating || 0) > 0 && (profile.googleRating || 0) < 3.5) { supportScore += 20; supportReasons.push('Avis clients faibles') }
  if (!profile.websiteHasLegalPages) { supportScore += 10; supportReasons.push('Absence pages service client') }
  scores.push({ agentId: 'support', agentName: 'Support Client', score: Math.min(supportScore, 100), reasons: supportReasons })

  // 5. Juridique
  let legalScore = 0
  const legalReasons: string[] = []
  if (!profile.websiteHasLegalPages) { legalScore += 30; legalReasons.push('Mentions légales absentes') }
  if (problem.match(/juridique|contrat|rgpd|conformité/)) { legalScore += 30; legalReasons.push('Défi juridique déclaré') }
  if (profile.country !== 'France') { legalScore += 10; legalReasons.push('Multi-pays → conformité complexe') }
  scores.push({ agentId: 'legal', agentName: 'Juridique', score: Math.min(legalScore, 100), reasons: legalReasons })

  // 6. Analytics
  let analyticsScore = 0
  const analyticsReasons: string[] = []
  if (problem.match(/données|analyser|kpi|tableau/)) { analyticsScore += 25; analyticsReasons.push('Défi data déclaré') }
  if (profile.revenue.includes('2M') || profile.revenue.includes('10M')) { analyticsScore += 20; analyticsReasons.push('Volume justifiant l\'analytics') }
  if (!tools.includes('analytics') && !tools.includes('google')) { analyticsScore += 15; analyticsReasons.push('Pas d\'outil analytics') }
  scores.push({ agentId: 'accounting', agentName: 'Comptabilité & Finance', score: Math.min(analyticsScore, 100), reasons: analyticsReasons })

  return scores.sort((a, b) => b.score - a.score)
}

// ─── PHASE 4: RAPPORT PERSONNALISÉ ────────────────────────

export function generateOnboardingReport(
  profile: EnrichedProfile,
  scores: AgentScore[],
  mainProblem: string
): string {
  const top3 = scores.slice(0, 3)
  const low3 = scores.slice(-3)

  return [
    `# 📊 Diagnostic Bapica — ${profile.companyName}`,
    '',
    `## 🏢 Votre profil`,
    `- **Secteur:** ${profile.sector}`,
    `- **Taille:** ${profile.employees}`,
    `- **CA:** ${profile.revenue}`,
    `- **Pays:** ${profile.country}${profile.city ? ` (${profile.city})` : ''}`,
    profile.website ? `- **Site:** ${profile.website}` : '',
    '',
    '## 🔍 Analyse automatique',
    profile.googleRating ? `- ⭐ Avis Google: ${profile.googleRating}/5 (${profile.googleReviews} avis)` : '',
    profile.websiteHasLegalPages ? '- ✅ Pages légales présentes' : '- ⚠️ Mentions légales absentes',
    profile.websiteMobile ? '- ✅ Site responsive' : '- ⚠️ Site non adapté mobile',
    profile.websiteHasBlog ? '- ✅ Blog actif' : '- ℹ️ Pas de blog détecté',
    '',
    `## 🎯 Votre défi: "${mainProblem}"`,
    '',
    '## 🤖 Agents recommandés',
    ...top3.map((s, i) => 
      `**${i + 1}. ${s.agentName}** (score: ${s.score}/100)\n${s.reasons.map(r => `   - ${r}`).join('\n')}`
    ),
    '',
    '## 💡 Recommandations immédiates',
    generateRecommendations(profile, scores),
  ].filter(Boolean).join('\n')
}

function generateRecommendations(profile: EnrichedProfile, scores: AgentScore[]): string {
  const recs: string[] = []
  
  if (!profile.websiteHasLegalPages) recs.push('1. **URGENT**: Ajoutez vos mentions légales et CGV — l\'agent Juridique peut vous aider')
  if (!profile.websiteMobile && profile.website) recs.push('2. **PRIORITAIRE**: Votre site n\'est pas mobile — vous perdez des clients')
  if ((profile.googleRating || 0) > 0 && (profile.googleRating || 0) < 4) recs.push('3. Améliorez vos avis Google — l\'agent Support peut structurer votre SAV')
  if (scores[0]?.score < 40) recs.push('💡 Votre entreprise semble déjà bien structurée — concentrez-vous sur la croissance')
  
  if (!recs.length) recs.push('✅ Aucune alerte majeure détectée')
  
  return recs.join('\n')
}
