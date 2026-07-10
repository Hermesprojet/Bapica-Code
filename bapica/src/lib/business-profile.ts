/**
 * Moteur d'Intelligence Business Bapica — v2.0
 * 
 * Analyse chaque PME en profondeur pour :
 * - Diagnostic stratégique automatisé
 * - Recommandations actionnables priorisées
 * - Estimation ROI et projections
 * - Scoring de maturité et risques
 * - Personnalisation continue via apprentissage
 */

// ============================================================
// TYPES
// ============================================================

export interface BusinessProfile {
  // Identité
  companyName?: string
  sector?: string
  subSector?: string
  
  // Structure
  companySize?: 'independant' | 'TPE' | 'PME' | 'ETI'
  employeeCount?: number
  foundedYear?: number
  
  // Finances
  monthlyRevenue?: string
  annualRevenue?: string
  businessModel?: 'b2b' | 'b2c' | 'b2b2c' | 'marketplace'
  
  // Maturité
  stage?: 'ideation' | 'early' | 'growth' | 'scaleup' | 'mature'
  maturityScore?: number       // 0-100
  digitalMaturity?: 'low' | 'medium' | 'high'
  
  // Objectifs & Priorités
  priorities: string[]
  shortTermGoal?: string
  longTermGoal?: string
  urgencyLevel?: 'low' | 'medium' | 'high' | 'critical'
  
  // Points de douleur
  painPoints: string[]
  timeWasters: string[]
  frustrationLevel?: number    // 0-10
  
  // Outils & Tech
  currentTools: string[]
  techStackMaturity?: 'low' | 'medium' | 'high'
  integrationComplexity?: 'simple' | 'moderate' | 'complex'
  
  // Clients & Marché
  customerAcquisition: string[]
  avgTicketSize?: string
  customerCount?: string
  churnRisk?: 'low' | 'medium' | 'high'
  
  // Concurrence
  competitiveAdvantage?: string
  marketPosition?: 'leader' | 'challenger' | 'niche' | 'newcomer'
  
  // Analyse IA
  profileSummary?: string
  strategicDiagnosis?: string
  recommendedAgents: string[]
  priorityActions: ActionPlan[]
  growthOpportunities: string[]
  riskFactors: RiskFactor[]
  roiEstimates: ROIEstimate[]
  industryBenchmarks: Benchmark[]
  nextSteps: string[]
}

export interface ActionPlan {
  action: string
  impact: 'low' | 'medium' | 'high' | 'transformational'
  effort: 'low' | 'medium' | 'high'
  timeframe: 'immediate' | '1-month' | '3-months' | '6-months'
  agentRecommended?: string
}

export interface RiskFactor {
  risk: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  probability: number  // 0-100
  mitigation: string
}

export interface ROIEstimate {
  area: string
  currentTimeSpent: string     // "10h/semaine"
  timeSaved: string            // "8h/semaine"
  costSaved: string            // "~400€/mois"
  agentInvolved: string
}

export interface Benchmark {
  metric: string
  yourValue: string
  industryAverage: string
  topPerformers: string
  opportunity: string
}

// ============================================================
// DONNÉES DE RÉFÉRENCE
// ============================================================

const INDUSTRY_DATA: Record<string, {
  label: string
  avgRevenue: string
  avgEmployees: number
  topChallenges: string[]
  digitalAdoption: 'low' | 'medium' | 'high'
  growthRate: string
}> = {
  ecommerce: {
    label: 'E-commerce',
    avgRevenue: '15-50k€/mois',
    avgEmployees: 2,
    topChallenges: ['Acquisition client', 'Logistique', 'Support client', 'SEO'],
    digitalAdoption: 'high',
    growthRate: '25-40%/an',
  },
  restauration: {
    label: 'Restauration',
    avgRevenue: '20-80k€/mois',
    avgEmployees: 5,
    topChallenges: ['Réservations', 'Avis clients', 'Gestion staff', 'Visibilité locale'],
    digitalAdoption: 'low',
    growthRate: '5-15%/an',
  },
  immobilier: {
    label: 'Immobilier',
    avgRevenue: '10-100k€/mois',
    avgEmployees: 3,
    topChallenges: ['Prospection vendeurs', 'Qualification leads', 'Visites', 'Suivi administratif'],
    digitalAdoption: 'medium',
    growthRate: '10-20%/an',
  },
  services: {
    label: 'Services & Conseil',
    avgRevenue: '10-60k€/mois',
    avgEmployees: 3,
    topChallenges: ['Prospection', 'Gestion projets', 'Facturation', 'Fidélisation'],
    digitalAdoption: 'medium',
    growthRate: '15-25%/an',
  },
  sante: {
    label: 'Santé',
    avgRevenue: '15-50k€/mois',
    avgEmployees: 4,
    topChallenges: ['RDV patients', 'Administratif', 'Réglementation', 'Urgences'],
    digitalAdoption: 'low',
    growthRate: '5-10%/an',
  },
  formation: {
    label: 'Formation',
    avgRevenue: '5-30k€/mois',
    avgEmployees: 2,
    topChallenges: ['Visibilité', 'Contenu pédagogique', 'Inscriptions', 'Suivi élèves'],
    digitalAdoption: 'medium',
    growthRate: '20-35%/an',
  },
  btp: {
    label: 'BTP & Artisanat',
    avgRevenue: '15-80k€/mois',
    avgEmployees: 6,
    topChallenges: ['Devis clients', 'Gestion chantiers', 'Appels manqués', 'Trésorerie'],
    digitalAdoption: 'low',
    growthRate: '5-15%/an',
  },
  saas: {
    label: 'SaaS / Tech',
    avgRevenue: '20-200k€/mois',
    avgEmployees: 8,
    topChallenges: ['Croissance MRR', 'Churn', 'Support technique', 'Product-market fit'],
    digitalAdoption: 'high',
    growthRate: '30-100%/an',
  },
  commerce: {
    label: 'Commerce local',
    avgRevenue: '10-40k€/mois',
    avgEmployees: 3,
    topChallenges: ['Visibilité locale', 'Fidélisation', 'Gestion stock', 'Saisonnalité'],
    digitalAdoption: 'low',
    growthRate: '3-10%/an',
  },
  freelance: {
    label: 'Freelance',
    avgRevenue: '3-10k€/mois',
    avgEmployees: 1,
    topChallenges: ['Prospection', 'Gestion temps', 'Admin/factures', 'Isolement'],
    digitalAdoption: 'medium',
    growthRate: '20-50%/an',
  },
  logistique: {
    label: 'Logistique',
    avgRevenue: '30-150k€/mois',
    avgEmployees: 10,
    topChallenges: ['Optimisation tournées', 'Suivi colis', 'Gestion flotte', 'Satisfaction client'],
    digitalAdoption: 'medium',
    growthRate: '10-25%/an',
  },
  finance: {
    label: 'Finance & Assurance',
    avgRevenue: '20-150k€/mois',
    avgEmployees: 5,
    topChallenges: ['Prospection B2B', 'Conformité', 'Gestion portefeuille', 'Relation client'],
    digitalAdoption: 'medium',
    growthRate: '10-20%/an',
  },
}

const AGENT_EFFICIENCY: Record<string, { timeSaved: string; costEquivalent: string; tasksAutomated: string }> = {
  general: { timeSaved: '3-5h/semaine', costEquivalent: '150-250€/mois', tasksAutomated: 'Coordination, recherche, synthèse' },
  support: { timeSaved: '10-20h/semaine', costEquivalent: '500-1000€/mois', tasksAutomated: 'Réponses clients, FAQ, tickets' },
  content: { timeSaved: '5-15h/semaine', costEquivalent: '400-800€/mois', tasksAutomated: 'Articles SEO, posts, scripts' },
  prospector: { timeSaved: '8-15h/semaine', costEquivalent: '500-1000€/mois', tasksAutomated: 'Prospection LinkedIn, qualification' },
  closer: { timeSaved: '5-10h/semaine', costEquivalent: '300-600€/mois', tasksAutomated: 'Relances, closing, objections' },
  telephone: { timeSaved: '15-30h/semaine', costEquivalent: '800-1500€/mois', tasksAutomated: 'Appels entrants, filtrage, RDV' },
  accounting: { timeSaved: '5-10h/semaine', costEquivalent: '300-500€/mois', tasksAutomated: 'Factures, relances, TVA' },
  video: { timeSaved: '3-8h/vidéo', costEquivalent: '200-500€/vidéo', tasksAutomated: 'Création vidéo, montage, voix' },
  recruiter: { timeSaved: '5-10h/recrutement', costEquivalent: '500-1000€/recrutement', tasksAutomated: 'Tri CV, offres, présélection' },
  legal: { timeSaved: '3-8h/semaine', costEquivalent: '300-600€/mois', tasksAutomated: 'Contrats, CGV, conformité' },
  analytics: { timeSaved: '3-6h/semaine', costEquivalent: '200-400€/mois', tasksAutomated: 'Dashboards, rapports, insights' },
  trends: { timeSaved: '2-4h/semaine', costEquivalent: '100-200€/mois', tasksAutomated: 'Veille marché, tendances, alertes' },
  scaling: { timeSaved: '5-10h/semaine', costEquivalent: '500-1000€/mois', tasksAutomated: 'Stratégie croissance, diagnostic' },
}

const AGENT_MAP: Record<string, string[]> = {
  ecommerce: ['content', 'support', 'telephone', 'analytics'],
  restauration: ['telephone', 'content', 'general', 'support'],
  immobilier: ['prospection-strategie', 'closer', 'telephone', 'content', 'legal'],
  services: ['legal', 'accounting', 'prospection-strategie', 'content', 'general'],
  sante: ['telephone', 'support', 'legal', 'accounting'],
  formation: ['content', 'video', 'support', 'general'],
  btp: ['telephone', 'accounting', 'legal', 'prospection-strategie'],
  saas: ['analytics', 'content', 'support', 'scaling', 'prospection-strategie'],
  commerce: ['content', 'telephone', 'support', 'general'],
  freelance: ['accounting', 'content', 'prospection-strategie', 'general'],
  logistique: ['telephone', 'analytics', 'accounting', 'support'],
  finance: ['prospection-strategie', 'closer', 'legal', 'analytics', 'scaling'],
}

// ============================================================
// ANALYSE PRINCIPALE
// ============================================================

export function analyzeBusinessProfile(data: any): BusinessProfile {
  const sector = data.activity || data.sector
  const industry = INDUSTRY_DATA[sector] || INDUSTRY_DATA.services
  
  const profile: BusinessProfile = {
    companyName: data.companyName || data.company_name || 'Votre entreprise',
    sector,
    companySize: data.companySize || 'TPE',
    employeeCount: data.employeeCount || 1,
    priorities: data.objectives || [],
    painPoints: data.adminTasks || [],
    currentTools: (data.apps || []).map((a: any) => a.name || a),
    customerAcquisition: data.contactMethods || [],
    recommendedAgents: [],
    growthOpportunities: [],
    riskFactors: [],
    timeWasters: [],
    priorityActions: [],
    roiEstimates: [],
    industryBenchmarks: [],
    nextSteps: [],
  }

  // ============================================================
  // 1. DIAGNOSTIC DE MATURITÉ
  // ============================================================
  
  // Business model
  if (['ecommerce', 'commerce'].includes(sector || '')) profile.businessModel = 'b2c'
  else if (['services', 'finance', 'saas'].includes(sector || '')) profile.businessModel = 'b2b'
  else if (['logistique'].includes(sector || '')) profile.businessModel = 'b2b2c'
  
  // Stade & maturité
  if ((profile.employeeCount || 0) <= 1) profile.stage = 'early'
  else if ((profile.employeeCount || 0) <= 10) profile.stage = 'growth'
  else if ((profile.employeeCount || 0) <= 50) profile.stage = 'scaleup'
  else profile.stage = 'mature'

  // Score de maturité digitale
  const advancedTools = ['hubspot', 'salesforce', 'stripe', 'shopify', 'n8n', 'zapier', 'make', 'notion']
  const hasAdvanced = advancedTools.some(t => profile.currentTools.some(ct => ct?.toLowerCase().includes(t)))
  profile.digitalMaturity = hasAdvanced ? 'high' : profile.currentTools.length > 3 ? 'medium' : 'low'
  profile.maturityScore = hasAdvanced ? 75 : profile.currentTools.length > 3 ? 45 : 20

  // Position sur le marché
  profile.marketPosition = profile.stage === 'early' ? 'newcomer' 
    : profile.stage === 'growth' ? 'challenger' 
    : profile.stage === 'scaleup' ? 'niche' 
    : 'leader'

  // Urgence
  const painCount = profile.painPoints.length
  profile.urgencyLevel = painCount >= 5 ? 'critical' : painCount >= 3 ? 'high' : painCount >= 1 ? 'medium' : 'low'
  profile.frustrationLevel = Math.min(10, painCount * 2)

  // ============================================================
  // 2. BENCHMARKS SECTORIELS
  // ============================================================
  
  profile.industryBenchmarks = [
    {
      metric: 'Croissance annuelle',
      yourValue: 'À calculer avec vos données',
      industryAverage: industry.growthRate,
      topPerformers: 'Top 10% : 2x la moyenne',
      opportunity: `Les leaders du secteur automatisent ${industry.digitalAdoption === 'low' ? 'la relation client' : 'leurs processus internes'}`,
    },
    {
      metric: 'Maturité digitale',
      yourValue: profile.digitalMaturity === 'high' ? 'Élevée' : profile.digitalMaturity === 'medium' ? 'Moyenne' : 'Faible',
      industryAverage: industry.digitalAdoption === 'high' ? 'Élevée' : industry.digitalAdoption === 'medium' ? 'Moyenne' : 'Faible',
      topPerformers: 'Élevée',
      opportunity: profile.digitalMaturity !== 'high' ? 'Automatiser pour rattraper le retard digital' : 'Optimiser les processus existants',
    },
    {
      metric: 'Taille d\'équipe',
      yourValue: `${profile.employeeCount || 1} personne(s)`,
      industryAverage: `${industry.avgEmployees} personnes`,
      topPerformers: `${Math.round(industry.avgEmployees * 1.5)} personnes`,
      opportunity: (profile.employeeCount || 0) < industry.avgEmployees ? 'Les agents IA peuvent compenser le manque d\'effectif' : 'Optimiser la productivité de l\'équipe existante',
    },
  ]

  // ============================================================
  // 3. RECOMMANDATIONS D'AGENTS
  // ============================================================
  
  profile.recommendedAgents = AGENT_MAP[sector || ''] || ['general', 'content', 'support']
  if (profile.stage === 'scaleup' || profile.stage === 'growth') {
    profile.recommendedAgents.push('scaling')
  }
  if (profile.customerAcquisition.includes('phone') || sector === 'btp' || sector === 'restauration') {
    if (!profile.recommendedAgents.includes('telephone')) profile.recommendedAgents.unshift('telephone')
  }

  // ============================================================
  // 4. PLAN D'ACTION PRIORITAIRE
  // ============================================================

  profile.priorityActions = [
    {
      action: `Activer l'agent ${profile.recommendedAgents[0] === 'telephone' ? 'Téléphonique' : profile.recommendedAgents[0]}`,
      impact: 'transformational',
      effort: 'low',
      timeframe: 'immediate',
      agentRecommended: profile.recommendedAgents[0],
    },
    {
      action: 'Connecter vos outils actuels à Bapica',
      impact: 'high',
      effort: 'medium',
      timeframe: '1-month',
    },
    {
      action: sector === 'ecommerce' ? 'Automatiser le support client et les fiches produits' 
        : sector === 'immobilier' ? 'Automatiser la prospection et le suivi leads'
        : sector === 'btp' ? 'Mettre en place le standard téléphonique IA'
        : sector === 'services' ? 'Automatiser la facturation et les relances'
        : 'Automatiser les tâches administratives principales',
      impact: 'high',
      effort: 'low',
      timeframe: '1-month',
    },
    {
      action: 'Mettre en place un dashboard de suivi performance',
      impact: 'medium',
      effort: 'low',
      timeframe: '3-months',
      agentRecommended: 'analytics',
    },
    {
      action: profile.stage !== 'mature' ? 'Déployer une stratégie de scaling automatisée' : 'Optimiser les processus existants',
      impact: 'transformational',
      effort: 'high',
      timeframe: '3-months',
      agentRecommended: 'scaling',
    },
  ]

  // ============================================================
  // 5. OPPORTUNITÉS DE CROISSANCE
  // ============================================================
  
  if (sector === 'ecommerce') {
    profile.growthOpportunities.push('Automatiser le support client → économiser 15-20h/semaine')
    profile.growthOpportunities.push('SEO produit à grande échelle → +30% trafic organique estimé')
    profile.growthOpportunities.push('Relances panier abandonné automatisées → +15% conversions')
  }
  if (sector === 'services') {
    profile.growthOpportunities.push('Prospection LinkedIn automatisée → 50+ leads qualifiés/mois')
    profile.growthOpportunities.push('Relance automatique des devis → +25% de conversion')
    profile.growthOpportunities.push('Automatisation facturation → 5-10h/semaine libérées')
  }
  if (['immobilier', 'btp'].includes(sector || '')) {
    profile.growthOpportunities.push('Agent téléphonique 24/7 → 0 appel perdu')
    profile.growthOpportunities.push('Suivi automatique des prospects → +30% de RDV honorés')
  }
  if (sector === 'saas') {
    profile.growthOpportunities.push('Analyse churn et rétention → réduire le churn de 20%')
    profile.growthOpportunities.push('Content marketing automatisé → +50% trafic blog')
    profile.growthOpportunities.push('Support client IA → diviser le temps de réponse par 10')
  }
  if (profile.digitalMaturity === 'low') {
    profile.growthOpportunities.push('Digitalisation des processus clés → économie estimée 200-500€/mois')
  }
  if (profile.employeeCount && profile.employeeCount <= 2) {
    profile.growthOpportunities.push('Les agents IA peuvent multiplier votre capacité par 3 sans recruter')
  }
  
  // Ajouter des opportunités génériques si pas assez
  if (profile.growthOpportunities.length < 3) {
    profile.growthOpportunities.push('Automatiser les tâches chronophages → récupérer 10h/semaine')
    profile.growthOpportunities.push('Déléguer le suivi client à un agent IA → satisfaction +40%')
  }

  // ============================================================
  // 6. ANALYSE DES RISQUES
  // ============================================================
  
  profile.riskFactors = []
  
  if (profile.digitalMaturity === 'low') {
    profile.riskFactors.push({
      risk: 'Retard digital critique',
      severity: 'high',
      probability: 80,
      mitigation: 'Déployer les agents IA progressivement, commencer par le plus impactant',
    })
  }
  if (profile.employeeCount && profile.employeeCount <= 2) {
    profile.riskFactors.push({
      risk: 'Dépendance au fondateur — risque de saturation',
      severity: 'critical',
      probability: 85,
      mitigation: 'Automatiser 80% des tâches répétitives via agents IA',
    })
  }
  if (!profile.customerAcquisition || profile.customerAcquisition.length <= 1) {
    profile.riskFactors.push({
      risk: 'Dépendance à un seul canal d\'acquisition',
      severity: 'high',
      probability: 60,
      mitigation: 'Activer les agents prospection et contenu pour diversifier',
    })
  }
  if (profile.companySize === 'TPE' && !profile.painPoints.some(p => p?.toLowerCase().includes('compta'))) {
    profile.riskFactors.push({
      risk: 'Gestion administrative non structurée',
      severity: 'medium',
      probability: 70,
      mitigation: 'Activer l\'agent Comptabilité pour structurer factures et relances',
    })
  }
  
  // Risque générique si pas assez
  if (profile.riskFactors.length < 2) {
    profile.riskFactors.push({
      risk: 'Sous-utilisation du potentiel d\'automatisation',
      severity: 'medium',
      probability: 50,
      mitigation: 'Suivre le plan d\'action prioritaire recommandé',
    })
  }

  // ============================================================
  // 7. ESTIMATION ROI
  // ============================================================
  
  profile.roiEstimates = []
  const agents = profile.recommendedAgents.slice(0, 4)
  let totalTimeSaved = 0
  let totalCostSaved = 0
  
  for (const agentId of agents) {
    const eff = AGENT_EFFICIENCY[agentId]
    if (eff) {
      const timeRange = eff.timeSaved.match(/(\d+)-(\d+)/)
      const avgTime = timeRange ? (parseInt(timeRange[1]) + parseInt(timeRange[2])) / 2 : 5
      const costRange = eff.costEquivalent.match(/(\d+)-(\d+)/)
      const avgCost = costRange ? (parseInt(costRange[1]) + parseInt(costRange[2])) / 2 : 300
      
      totalTimeSaved += avgTime
      totalCostSaved += avgCost
      
      profile.roiEstimates.push({
        area: eff.tasksAutomated,
        currentTimeSpent: `${Math.round(avgTime * 1.5)}h/semaine`,
        timeSaved: eff.timeSaved,
        costSaved: eff.costEquivalent,
        agentInvolved: agentId,
      })
    }
  }
  
  // Synthèse ROI
  if (profile.roiEstimates.length > 0) {
    profile.roiEstimates.push({
      area: 'TOTAL ÉCONOMIES ESTIMÉES',
      currentTimeSpent: `${Math.round(totalTimeSaved * 1.2)}h/semaine`,
      timeSaved: `${Math.round(totalTimeSaved)}h/semaine`,
      costSaved: `${Math.round(totalCostSaved)}€/mois`,
      agentInvolved: 'équipe',
    })
  }

  // ============================================================
  // 8. PROCHAINES ÉTAPES
  // ============================================================
  
  profile.nextSteps = [
    'Compléter votre profil business avec plus de détails',
    `Activer ${profile.recommendedAgents[0]} — l'agent le plus impactant pour votre secteur`,
    'Connecter vos outils principaux (CRM, email, calendrier)',
    'Tester un agent en condition réelle sur une tâche simple',
    'Revoir le dashboard dans 7 jours pour mesurer les premiers résultats',
  ]

  // ============================================================
  // 9. RÉSUMÉ STRATÉGIQUE
  // ============================================================
  
  profile.strategicDiagnosis = [
    `${profile.companyName} est une ${profile.companySize} du secteur ${industry.label},`,
    `au stade ${profile.stage === 'early' ? 'de démarrage' : profile.stage === 'growth' ? 'de croissance' : profile.stage === 'scaleup' ? 'de passage à l\'échelle' : 'de maturité'}.`,
    `Maturité digitale : ${profile.digitalMaturity === 'high' ? 'élevée' : profile.digitalMaturity === 'medium' ? 'moyenne' : 'faible'} (score ${profile.maturityScore}/100).`,
    `${profile.riskFactors.length} risques identifiés, ${profile.riskFactors.filter(r => r.severity === 'critical' || r.severity === 'high').length} prioritaires.`,
    `Potentiel d'automatisation : ${Math.round(totalTimeSaved)}h/semaine libérables, ~${Math.round(totalCostSaved)}€/mois d'économies estimées.`,
    `Plan d'action : ${profile.priorityActions.length} actions priorisées sur ${profile.priorityActions[0]?.timeframe === 'immediate' ? 'immédiat' : '1 mois'}.`,
  ].join(' ')

  profile.profileSummary = profile.strategicDiagnosis

  return profile
}
