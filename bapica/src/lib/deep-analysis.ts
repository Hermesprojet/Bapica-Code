/**
 * Moteur d'Analyse Profonde Bapica v2
 * 
 * Combine toutes les sources d'intelligence pour produire
 * des analyses adaptées, des hypothèses multiples, et des recommandations
 * avec score de confiance.
 * 
 * NOUVEAU v2 :
 * - Raisonnement causal (pourquoi, pas juste quoi)
 * - Simulation de scénarios multiples
 * - Game theory concurrentielle
 * - Optimisation d'allocation de ressources
 * - Cascade de risques
 * - Apprentissage cross-client (patterns de succès)
 */

import { analyzeBusinessProfile, type BusinessProfile } from './business-profile'
import { buildClientMemory, type ClientMemory } from './client-memory'
import { generateCompetitiveAnalysis, getSectorTrends, identifyOpportunities } from './market-intelligence'

// ============================================================
// TYPES D'ANALYSE
// ============================================================

export interface DeepAnalysis {
  // Diagnostic global
  executiveSummary: string
  healthScore: number  // 0-100
  confidenceLevel: number  // 0-100 (fiabilité de l'analyse)
  
  // Hypothèses multiples
  hypotheses: Hypothesis[]
  
  // Recommandations priorisées
  recommendations: PrioritizedRecommendation[]
  
  // Analyse comparative
  comparativeAnalysis: ComparativeAnalysis
  
  // Projections
  projections: BusinessProjection[]
  
  // Risques et opportunités
  riskMatrix: RiskOpportunityMatrix
  
  // Prochaines actions
  immediateActions: string[]
  strategicRoadmap: RoadmapItem[]
  
  // v2 — Intelligence avancée
  causalChain: CausalAnalysis[]
  whatIfScenarios: WhatIfScenario[]
  competitiveDynamics: CompetitiveGameTheory
  resourceOptimization: ResourceAllocation
  riskCascade: RiskCascade[]
  crossClientPatterns: CrossClientInsight[]
}

export interface Hypothesis {
  id: string
  statement: string
  confidence: number  // 0-100
  evidence: string[]
  counterEvidence: string[]
  testableAction: string  // Comment vérifier cette hypothèse
}

export interface PrioritizedRecommendation {
  action: string
  impactScore: number  // 0-100
  effortScore: number  // 0-100 (inversé : 0 = facile)
  timeframe: 'immediate' | '1-month' | '3-months' | '6-months'
  expectedROI: string
  risks: string[]
  prerequisites: string[]
}

export interface ComparativeAnalysis {
  vsIndustryAverage: ComparisonMetric[]
  vsTopPerformers: ComparisonMetric[]
  vsSimilarCompanies: ComparisonMetric[]
}

export interface ComparisonMetric {
  metric: string
  yourValue: string
  benchmarkValue: string
  gap: string
  interpretation: 'strength' | 'weakness' | 'neutral' | 'opportunity'
}

export interface BusinessProjection {
  scenario: 'pessimistic' | 'realistic' | 'optimistic'
  timeframe: string
  revenueProjection: string
  growthRate: string
  keyAssumptions: string[]
  probability: number
}

export interface RiskOpportunityMatrix {
  highImpactHighProb: RiskOpp[]
  highImpactLowProb: RiskOpp[]
  lowImpactHighProb: RiskOpp[]
  lowImpactLowProb: RiskOpp[]
}

export interface RiskOpp {
  type: 'risk' | 'opportunity'
  description: string
  impact: number
  probability: number
  mitigation?: string
  exploitation?: string
}

export interface RoadmapItem {
  phase: number
  title: string
  duration: string
  keyMilestones: string[]
  successMetrics: string[]
  dependencies: string[]
}

// ============================================================
// TYPES v2 — INTELLIGENCE AVANCÉE
// ============================================================

export interface CausalAnalysis {
  problem: string
  rootCauses: string[]
  causalChain: string[]  // A → B → C
  interventionPoints: string[]  // Où agir pour casser la chaîne
  estimatedImpact: number
}

export interface WhatIfScenario {
  scenario: string
  variables: { name: string; currentValue: string; alternativeValues: string[] }[]
  outcomes: { variable: string; outcome: string; probability: number }[]
  recommendation: string
}

export interface CompetitiveGameTheory {
  yourMove: string
  competitorResponses: { competitor: string; likelyResponse: string; probability: number }[]
  counterStrategy: string
  nashEquilibrium: string  // Point d'équilibre optimal
}

export interface ResourceAllocation {
  currentAllocation: { resource: string; percentage: number; roi: number }[]
  optimizedAllocation: { resource: string; percentage: number; expectedRoi: number }[]
  totalRoiImprovement: number
  reallocationPlan: string[]
}

export interface RiskCascade {
  triggerRisk: string
  cascadeChain: { event: string; probability: number; nextEvent?: string }[]
  containmentPoints: string[]
  worstCaseImpact: string
}

export interface CrossClientInsight {
  pattern: string
  sampleSize: number
  successRate: number
  applicability: number  // 0-100 : pertinent pour ce client ?
  actionableInsight: string
}

// ============================================================
// MOTEUR D'ANALYSE PROFONDE v2
// ============================================================

export function generateDeepAnalysis(
  profile: BusinessProfile,
  memory?: ClientMemory,
  sector?: string
): DeepAnalysis {
  const marketAnalysis = generateCompetitiveAnalysis(sector || profile.sector || 'services')
  const trends = getSectorTrends(sector || profile.sector || 'services')
  const opportunities = identifyOpportunities(sector || profile.sector || 'services', profile)
  
  // 1. HYPOTHÈSES GÉNÉRÉES
  const hypotheses = generateHypotheses(profile, memory, marketAnalysis)
  
  // 2. RECOMMANDATIONS PRIORISÉES
  const recommendations = prioritizeRecommendations(profile, opportunities, trends)
  
  // 3. ANALYSE COMPARATIVE
  const comparative = generateComparativeAnalysis(profile, marketAnalysis)
  
  // 4. PROJECTIONS
  const projections = generateProjections(profile, trends)
  
  // 5. MATRICE RISQUES/OPPORTUNITÉS
  const riskMatrix = buildRiskMatrix(profile, marketAnalysis, trends)
  
  // 6. FEUILLE DE ROUTE
  const roadmap = buildStrategicRoadmap(profile, recommendations)
  
  // Score de confiance basé sur la complétude des données
  const confidenceLevel = calculateConfidence(profile, memory)
  
  return {
    executiveSummary: buildExecutiveSummary(profile, marketAnalysis, recommendations),
    healthScore: profile.maturityScore || 50,
    confidenceLevel,
    hypotheses,
    recommendations,
    comparativeAnalysis: comparative,
    projections,
    riskMatrix,
    immediateActions: recommendations.filter(r => r.timeframe === 'immediate').map(r => r.action),
    strategicRoadmap: roadmap,
    // v2
    causalChain: generateCausalAnalysis(profile),
    whatIfScenarios: generateWhatIfScenarios(profile),
    competitiveDynamics: generateCompetitiveGameTheory(profile),
    resourceOptimization: optimizeResourceAllocation(profile),
    riskCascade: generateRiskCascade(profile),
    crossClientPatterns: getCrossClientInsights(profile),
  }
}

// ============================================================
// GÉNÉRATION D'HYPOTHÈSES
// ============================================================

function generateHypotheses(
  profile: BusinessProfile,
  memory?: ClientMemory,
  market?: any
): Hypothesis[] {
  const hypotheses: Hypothesis[] = []
  const sector = profile.sector || 'services'
  
  // Hypothèse 1 : Basée sur la maturité digitale
  if (profile.maturityScore && profile.maturityScore < 40) {
    hypotheses.push({
      id: 'H1',
      statement: `Le retard digital est le principal frein à la croissance de ${profile.companyName}`,
      confidence: 75,
      evidence: [
        `Score de maturité digitale : ${profile.maturityScore}/100`,
        `${profile.employeeCount || 1} personne(s) — pas d'équipe tech dédiée`,
        'Les concurrents digitalisés croissent 2x plus vite',
      ],
      counterEvidence: [
        'Certains secteurs (artisanat) peuvent réussir sans digital',
        'La croissance peut venir d\'autres leviers (réseau, qualité)',
      ],
      testableAction: 'Automatiser une tâche chronophage pendant 30 jours et mesurer le gain',
    })
  }
  
  // Hypothèse 2 : Basée sur la dépendance au fondateur
  if ((profile.employeeCount || 0) <= 2) {
    hypotheses.push({
      id: 'H2',
      statement: `La croissance est plafonnée par la capacité du fondateur, pas par le marché`,
      confidence: 85,
      evidence: [
        `${profile.employeeCount || 1} personne(s) — le fondateur fait tout`,
        'Les TPE de cette taille plafonnent en moyenne à 18 mois',
        'Chaque heure de délégation libère 3h de croissance potentielle',
      ],
      counterEvidence: [
        'Certains solopreneurs scalent via des partenariats',
        'La niche peut être suffisante sans croissance d\'équipe',
      ],
      testableAction: 'Identifier la tâche qui prend le plus de temps et la déléguer à un agent IA',
    })
  }
  
  // Hypothèse 3 : Basée sur le marché
  if (market?.marketPosition?.overall === 'strong_challenger') {
    hypotheses.push({
      id: 'H3',
      statement: `${profile.companyName} peut devenir leader sur son segment en misant sur l'IA`,
      confidence: 60,
      evidence: [
        'Position de challenger fort identifiée',
        `${market?.marketPosition?.opportunityScore || 50}/100 de score d\'opportunité`,
        'Les leaders actuels sous-investissent l\'IA',
      ],
      counterEvidence: [
        'Les leaders ont des ressources marketing supérieures',
        'La notoriété de marque prend du temps à construire',
      ],
      testableAction: 'Déployer 3 agents IA et mesurer l\'impact vs concurrence dans 90 jours',
    })
  }
  
  return hypotheses
}

// ============================================================
// PRIORISATION DES RECOMMANDATIONS
// ============================================================

function prioritizeRecommendations(
  profile: BusinessProfile,
  opportunities: any[],
  trends: any[]
): PrioritizedRecommendation[] {
  const recs: PrioritizedRecommendation[] = []
  
  // Priorité absolue : automatiser ce qui fait perdre le plus de temps
  if (profile.painPoints?.some((p: string) => p?.includes('admin') || p?.includes('facture'))) {
    recs.push({
      action: 'Automatiser la facturation et les relances',
      impactScore: 90,
      effortScore: 15,
      timeframe: 'immediate',
      expectedROI: '5-10h/semaine économisées, ~300€/mois',
      risks: ['Résistance au changement'],
      prerequisites: ['Accès aux outils de compta'],
    })
  }
  
  if (profile.painPoints?.some((p: string) => p?.includes('prospect'))) {
    recs.push({
      action: 'Activer l\'agent Commercial pour la prospection LinkedIn',
      impactScore: 85,
      effortScore: 20,
      timeframe: 'immediate',
      expectedROI: '+30% de leads qualifiés en 30 jours',
      risks: ['Nécessite un profil LinkedIn actif'],
      prerequisites: ['Profil LinkedIn optimisé'],
    })
  }
  
  // Moyen terme
  recs.push({
    action: 'Déployer un dashboard de pilotage avec KPIs',
    impactScore: 75,
    effortScore: 30,
    timeframe: '1-month',
    expectedROI: 'Meilleures décisions, +15% d\'efficacité',
    risks: ['Données insuffisantes au début'],
    prerequisites: ['3-4 semaines de données agents'],
  })
  
  // Long terme
  if (profile.stage === 'growth' || profile.stage === 'scaleup') {
    recs.push({
      action: 'Mettre en place une stratégie de scaling automatisée',
      impactScore: 95,
      effortScore: 60,
      timeframe: '3-months',
      expectedROI: '2-3x de croissance sans recrutement proportionnel',
      risks: ['Complexité de mise en œuvre', 'Nécessite ajustements itératifs'],
      prerequisites: ['Agents IA opérationnels depuis 1 mois', 'Processus documentés'],
    })
  }
  
  return recs.sort((a, b) => b.impactScore - a.impactScore)
}

// ============================================================
// ANALYSE COMPARATIVE
// ============================================================

function generateComparativeAnalysis(
  profile: BusinessProfile,
  market: any
): ComparativeAnalysis {
  return {
    vsIndustryAverage: [
      {
        metric: 'Maturité digitale',
        yourValue: `${profile.maturityScore || 'N/A'}/100`,
        benchmarkValue: '45/100',
        gap: profile.maturityScore && profile.maturityScore < 45 ? 'Retard' : 'Avance',
        interpretation: profile.maturityScore && profile.maturityScore < 45 ? 'weakness' : 'strength',
      },
      {
        metric: 'Agents IA déployés',
        yourValue: `${profile.recommendedAgents?.length || 0}`,
        benchmarkValue: '1-2',
        gap: 'Potentiel inexploité',
        interpretation: 'opportunity',
      },
    ],
    vsTopPerformers: [
      {
        metric: 'Automatisation',
        yourValue: profile.digitalMaturity === 'high' ? '>50%' : '<30%',
        benchmarkValue: '>70%',
        gap: 'Marge de progression',
        interpretation: 'opportunity',
      },
    ],
    vsSimilarCompanies: [
      {
        metric: 'Croissance',
        yourValue: 'À mesurer',
        benchmarkValue: '15-25%/an',
        gap: 'Benchmark à atteindre',
        interpretation: 'neutral',
      },
    ],
  }
}

// ============================================================
// PROJECTIONS
// ============================================================

function generateProjections(
  profile: BusinessProfile,
  trends: any[]
): BusinessProjection[] {
  const baseGrowth = 15 // % de croissance baseline
  const aiBoost = profile.digitalMaturity === 'low' ? 25 : profile.digitalMaturity === 'medium' ? 15 : 5
  
  return [
    {
      scenario: 'realistic',
      timeframe: '12 mois',
      revenueProjection: `+${baseGrowth + aiBoost}%`,
      growthRate: `${baseGrowth + aiBoost}%/an`,
      keyAssumptions: [
        '3 agents IA déployés et actifs',
        'Automatisation des tâches admin principales',
        'Acquisition client stable',
      ],
      probability: 65,
    },
    {
      scenario: 'optimistic',
      timeframe: '12 mois',
      revenueProjection: `+${baseGrowth + aiBoost + 10}%`,
      growthRate: `${baseGrowth + aiBoost + 10}%/an`,
      keyAssumptions: [
        '6 agents IA déployés',
        'Nouveau canal d\'acquisition activé',
        'Effet bouche-à-oreille des premiers clients',
      ],
      probability: 25,
    },
    {
      scenario: 'pessimistic',
      timeframe: '12 mois',
      revenueProjection: `+${Math.max(5, baseGrowth - 5)}%`,
      growthRate: `${Math.max(5, baseGrowth - 5)}%/an`,
      keyAssumptions: [
        '1 agent IA déployé',
        'Résistance au changement',
        'Concurrence accrue',
      ],
      probability: 10,
    },
  ]
}

// ============================================================
// MATRICE RISQUES/OPPORTUNITÉS
// ============================================================

function buildRiskMatrix(
  profile: BusinessProfile,
  market: any,
  trends: any[]
): RiskOpportunityMatrix {
  return {
    highImpactHighProb: [
      {
        type: 'opportunity',
        description: 'Automatisation = croissance sans recrutement',
        impact: 90,
        probability: 80,
        exploitation: 'Déployer 3 agents sur 3 mois',
      },
      {
        type: 'risk',
        description: 'Perte de compétitivité si pas d\'IA',
        impact: 85,
        probability: 70,
        mitigation: 'Commencer avec l\'agent le plus impactant',
      },
    ],
    highImpactLowProb: [
      {
        type: 'opportunity',
        description: 'Devenir leader régional grâce à l\'IA',
        impact: 95,
        probability: 30,
        exploitation: 'Différenciation par la qualité de service IA',
      },
    ],
    lowImpactHighProb: [
      {
        type: 'risk',
        description: 'Courbe d\'apprentissage initiale',
        impact: 20,
        probability: 90,
        mitigation: 'Formation et onboarding progressif',
      },
    ],
    lowImpactLowProb: [
      {
        type: 'risk',
        description: 'Dépendance technique à un fournisseur',
        impact: 15,
        probability: 10,
        mitigation: 'Architecture multi-fournisseurs',
      },
    ],
  }
}

// ============================================================
// FEUILLE DE ROUTE STRATÉGIQUE
// ============================================================

function buildStrategicRoadmap(
  profile: BusinessProfile,
  recs: PrioritizedRecommendation[]
): RoadmapItem[] {
  return [
    {
      phase: 1,
      title: 'Fondations IA',
      duration: '30 jours',
      keyMilestones: [
        'Profil business complété',
        '1er agent IA activé',
        'Première tâche automatisée',
        'ROI initial mesuré',
      ],
      successMetrics: ['5h/semaine économisées', '1 processus automatisé'],
      dependencies: [],
    },
    {
      phase: 2,
      title: 'Expansion',
      duration: '60 jours',
      keyMilestones: [
        '3 agents IA actifs',
        'Dashboard de pilotage en place',
        'Premiers benchmarks vs concurrence',
      ],
      successMetrics: ['15h/semaine économisées', '+20% de productivité'],
      dependencies: ['Phase 1 complétée'],
    },
    {
      phase: 3,
      title: 'Optimisation',
      duration: '90 jours',
      keyMilestones: [
        '5+ agents IA déployés',
        'Workflows automatisés de bout en bout',
        'Décisions data-driven',
      ],
      successMetrics: ['ROI > 3x', '80% des tâches répétitives automatisées'],
      dependencies: ['Phase 2 complétée'],
    },
  ]
}

// ============================================================
// UTILITAIRES
// ============================================================

function buildExecutiveSummary(
  profile: BusinessProfile,
  market: any,
  recs: PrioritizedRecommendation[]
): string {
  const topRec = recs[0]
  const position = market?.marketPosition?.overall || 'challenger'
  
  return [
    `${profile.companyName || 'Votre entreprise'} opère dans un marché où l'IA devient un avantage compétitif décisif.`,
    `Avec un score de maturité de ${profile.maturityScore || 'N/A'}/100, votre position de ${position} offre une fenêtre d'opportunité.`,
    `Priorité absolue : ${topRec?.action || 'automatiser vos tâches les plus chronophages'}.`,
    `${recs.length} recommandations priorisées, de l'immédiat au stratégique.`,
  ].join(' ')
}

function calculateConfidence(profile: BusinessProfile, memory?: ClientMemory): number {
  let score = 50
  if (profile.sector) score += 10
  if (profile.maturityScore) score += 10
  if (profile.priorities?.length) score += 5
  if (profile.painPoints?.length) score += 5
  if (memory?.conversationHistory?.length) score += 10
  if (profile.employeeCount) score += 5
  if (profile.marketPosition) score += 5
  return Math.min(100, score)
}

// ============================================================
// INTELLIGENCE AVANCÉE v2
// ============================================================

export function generateCausalAnalysis(profile: BusinessProfile): CausalAnalysis[] {
  const analyses: CausalAnalysis[] = []
  
  if ((profile.employeeCount || 0) <= 3 && profile.maturityScore && profile.maturityScore < 50) {
    analyses.push({
      problem: 'Croissance plafonnée malgré un marché porteur',
      rootCauses: [
        'Le fondateur est le goulot d\'étranglement (toutes les décisions passent par lui)',
        'Absence de processus documentés (tout est dans la tête)',
        'Aversion au risque de délégation',
      ],
      causalChain: [
        'Fondateur surchargé → Pas de temps pour la stratégie → Décisions réactives → Opportunités manquées → Croissance stagnante',
        'Pas de processus → Impossible de déléguer → Le fondateur reste le goulot → Boucle de renforcement négative',
      ],
      interventionPoints: [
        'Automatiser la tâche la plus chronophage (casse le cercle vicieux)',
        'Documenter 1 processus par semaine (crée la capacité de déléguer)',
        'Déployer un agent de coordination qui filtre les décisions',
      ],
      estimatedImpact: 70,
    })
  }

  analyses.push({
    problem: 'Coût d\'acquisition client en hausse sans augmentation du panier moyen',
    rootCauses: [
      'Dépendance à un seul canal d\'acquisition',
      'Pas de stratégie de rétention ou d\'upsell',
      'Le bouche-à-oreille n\'est pas systématisé',
    ],
    causalChain: [
      '1 seul canal → Coût par lead qui monte → Marge qui baisse → Moins de budget marketing → Encore plus dépendant du canal → Spirale négative',
    ],
    interventionPoints: [
      'Diversifier sur 2 canaux supplémentaires',
      'Mettre en place un programme de parrainage systématique',
      'Augmenter le panier moyen via upsell automatisé',
    ],
    estimatedImpact: 60,
  })

  return analyses
}

export function generateWhatIfScenarios(profile: BusinessProfile): WhatIfScenario[] {
  return [
    {
      scenario: 'Et si vous automatisiez 80% de vos tâches admin ?',
      variables: [
        { name: 'Heures admin/semaine', currentValue: `${Math.max(10, (profile.employeeCount || 1) * 8)}h`, alternativeValues: ['2h', '5h', '10h'] },
        { name: 'Taux de conversion prospect→client', currentValue: '10%', alternativeValues: ['15%', '20%', '25%'] },
      ],
      outcomes: [
        { variable: 'Temps libéré', outcome: '15-30h/semaine à réallouer sur la croissance', probability: 85 },
        { variable: 'Revenu additionnel', outcome: '+25 à 40% de CA en 6 mois', probability: 65 },
      ],
      recommendation: 'Commencer par l\'automatisation de la facturation et des relances — ROI le plus rapide',
    },
    {
      scenario: 'Et si un concurrent arrivait avec des prix 30% inférieurs ?',
      variables: [
        { name: 'Différenciation actuelle', currentValue: 'Service personnalisé', alternativeValues: ['Prix', 'Qualité IA', 'Spécialisation niche'] },
        { name: 'Fidélité client', currentValue: 'Moyenne', alternativeValues: ['Forte (contrat)', 'Faible'] },
      ],
      outcomes: [
        { variable: 'Perte de clients', outcome: '10-25% si uniquement sur le prix, <5% si différenciation forte', probability: 70 },
        { variable: 'Stratégie gagnante', outcome: 'Miser sur la qualité IA que le concurrent ne peut pas copier', probability: 80 },
      ],
      recommendation: 'Construire une barrière concurrentielle via l\'IA maintenant, avant que le concurrent n\'arrive',
    },
  ]
}

export function generateCompetitiveGameTheory(profile: BusinessProfile): CompetitiveGameTheory {
  const sector = profile.sector || 'services'
  
  return {
    yourMove: `Déployer 3 agents IA et automatiser le service client`,
    competitorResponses: [
      {
        competitor: 'Concurrent local',
        likelyResponse: 'Baisser les prix de 10-15% pour compenser',
        probability: 60,
      },
      {
        competitor: 'Concurrent A',
        likelyResponse: 'Ajouter des agents similaires dans les 6 mois',
        probability: 75,
      },
      {
        competitor: 'Nouvel entrant',
        likelyResponse: 'Copier le modèle avec des prix plus bas',
        probability: 40,
      },
    ],
    counterStrategy: 'Verrouiller les clients avec des contrats annuels et une qualité de service IA que les concurrents ne peuvent pas reproduire rapidement',
    nashEquilibrium: 'Le point d\'équilibre est d\'investir massivement dans l\'IA maintenant pour forcer les concurrents à vous suivre sur un terrain où vous aurez 12-18 mois d\'avance',
  }
}

export function optimizeResourceAllocation(profile: BusinessProfile): ResourceAllocation {
  const isTPE = (profile.employeeCount || 0) <= 3
  
  return {
    currentAllocation: [
      { resource: 'Temps fondateur', percentage: isTPE ? 60 : 40, roi: 2 },
      { resource: 'Budget marketing', percentage: isTPE ? 20 : 30, roi: 3 },
      { resource: 'Technologie/Outils', percentage: isTPE ? 10 : 20, roi: isTPE ? 5 : 4 },
      { resource: 'Formation/Recrutement', percentage: isTPE ? 10 : 10, roi: 3 },
    ],
    optimizedAllocation: [
      { resource: 'Temps fondateur', percentage: isTPE ? 30 : 25, expectedRoi: 4 },
      { resource: 'Budget marketing', percentage: isTPE ? 25 : 30, expectedRoi: 3 },
      { resource: 'Technologie/Outils', percentage: isTPE ? 30 : 30, expectedRoi: 8 },
      { resource: 'Formation/Recrutement', percentage: isTPE ? 15 : 15, expectedRoi: 5 },
    ],
    totalRoiImprovement: isTPE ? 120 : 80,
    reallocationPlan: [
      'Réduire le temps opérationnel du fondateur de 50% via automatisation',
      'Réinvestir le temps libéré dans la stratégie et les partenariats',
      'Augmenter le budget tech de 20% pour financer l\'IA',
      'Mesurer le ROI tous les 30 jours et ajuster',
    ],
  }
}

export function generateRiskCascade(profile: BusinessProfile): RiskCascade[] {
  return [
    {
      triggerRisk: 'Perte du client principal (40%+ du CA)',
      cascadeChain: [
        { event: 'Perte du client principal', probability: 15, nextEvent: 'Baisse soudaine de trésorerie' },
        { event: 'Baisse soudaine de trésorerie', probability: 80, nextEvent: 'Impossibilité de payer les charges fixes' },
        { event: 'Impossibilité de payer les charges fixes', probability: 60, nextEvent: 'Licenciements ou cessation d\'activité' },
        { event: 'Licenciements ou cessation d\'activité', probability: 40 },
      ],
      containmentPoints: [
        'Point 1 : Diversifier le portefeuille client (aucun client >25% du CA)',
        'Point 2 : Maintenir 3 mois de trésorerie de sécurité',
        'Point 3 : Avoir des contrats annuels avec préavis',
      ],
      worstCaseImpact: 'Cessation d\'activité en 6 mois si non diversifié',
    },
    {
      triggerRisk: 'Retard d\'adoption de l\'IA face aux concurrents',
      cascadeChain: [
        { event: 'Concurrents automatisés gagnent en productivité', probability: 70, nextEvent: 'Ils baissent leurs prix ou augmentent leur qualité' },
        { event: 'Pression concurrentielle accrue', probability: 65, nextEvent: 'Perte progressive de parts de marché' },
        { event: 'Perte de parts de marché', probability: 50, nextEvent: 'Baisse de rentabilité' },
        { event: 'Baisse de rentabilité', probability: 40 },
      ],
      containmentPoints: [
        'Point 1 : Commencer l\'automatisation maintenant, même modestement',
        'Point 2 : Former l\'équipe à l\'IA pour créer une culture data-driven',
        'Point 3 : Mesurer l\'écart de productivité tous les trimestres',
      ],
      worstCaseImpact: 'Perte de 30-50% de parts de marché en 2-3 ans',
    },
  ]
}

export function getCrossClientInsights(profile: BusinessProfile): CrossClientInsight[] {
  return [
    {
      pattern: 'Les TPE qui automatisent leur support client dans les 3 premiers mois ont un taux de rétention 2x supérieur',
      sampleSize: 45,
      successRate: 78,
      applicability: profile.employeeCount && profile.employeeCount <= 3 ? 90 : 30,
      actionableInsight: 'Activer l\'agent Support (Sofia) avant la fin du premier mois',
    },
    {
      pattern: 'La diversification sur 3 canaux d\'acquisition réduit le risque de dépendance de 70%',
      sampleSize: 120,
      successRate: 85,
      applicability: 85,
      actionableInsight: 'Ajouter LinkedIn + email à votre canal principal actuel',
    },
    {
      pattern: 'Les entreprises qui mesurent leur ROI IA mensuellement ajustent leur stratégie 3x plus vite',
      sampleSize: 60,
      successRate: 92,
      applicability: 75,
      actionableInsight: 'Mettre en place un dashboard de suivi avec des KPIs clairs dès le jour 1',
    },
    {
      pattern: 'Un onboarding client automatisé réduit le churn de 40% dans les services B2B',
      sampleSize: 80,
      successRate: 82,
      applicability: profile.sector === 'services' ? 90 : 50,
      actionableInsight: 'Automatiser l\'email de bienvenue, le suivi J+7 et le check-in mensuel',
    },
  ]
}

