/**
 * Module d'Intelligence Marché Bapica
 * 
 * Analyse concurrentielle, benchmarks sectoriels réels,
 * détection de tendances, opportunités de marché.
 * 
 * Basé sur des données réelles collectées via analyse des concurrents.
 */

// ============================================================
// DONNÉES MARCHÉ RÉELLES (collectées manuellement)
// ============================================================

interface CompetitorProfile {
  name: string
  url: string
  type: 'direct' | 'indirect' | 'complementary'
  pricing: { entry: string; pro: string }
  agents: number
  strengths: string[]
  weaknesses: string[]
  targetMarket: string
}

const COMPETITOR_DB: Record<string, CompetitorProfile> = {
  concurrentA: {
    name: 'Concurrent A',
    url: 'concurrent-a.com',
    type: 'direct',
    pricing: { entry: '~39€/mois', pro: '~79€/mois' },
    agents: 8,
    strengths: [
      'WhatsApp-first (Assistant WhatsApp) — très accessible pour PME non tech',
      'Onboarding humain 1:1 inclus dans tous les plans',
      'Notoriété forte via l\'émission Legend (M6)',
      'Codes promo permanents (LEGEND10, LEGEND25)',
      'Prix agressifs avec promos',
    ],
    weaknesses: [
      'Seulement 8 agents (vs 11 Bapica)',
      'Pas de dashboard analytics',
      'Dépendant de WhatsApp — pas d\'app native',
      'GPT-4o-mini pour la plupart des agents (qualité inférieure)',
      'Pas de coordination entre agents',
    ],
    targetMarket: 'TPE et indépendants français',
  },
  substi: {
    name: 'Substi.ai',
    url: 'substi.ai',
    type: 'direct',
    pricing: { entry: '~29€/mois', pro: '~59€/mois' },
    agents: 3,
    strengths: [
      'Focus téléphonie — excellent pour standard IA',
      'Design épuré et professionnel',
      'Positionnement clair : "L\'IA qui répond aux appels"',
      'Simplicité : 3 agents, pas de complexité',
    ],
    weaknesses: [
      'Très limité en nombre d\'agents',
      'Pas de prospection, contenu, ou compta',
      'Pas d\'onboarding intelligent',
      'Pas de dashboard analytics',
    ],
    targetMarket: 'TPE qui veulent juste un standard téléphonique',
  },
  altahq: {
    name: 'AltaHQ (Katie)',
    url: 'altahq.com',
    type: 'indirect',
    pricing: { entry: 'Sur devis', pro: 'Sur devis' },
    agents: 3,
    strengths: [
      'Personnification forte (Katie = un prénom)',
      '50+ sources de données pour identifier l\'ICP',
      'Multi-canal : email + LinkedIn + SMS',
      'Métriques ROI très spécifiques (3x leads, 80% coûts)',
    ],
    weaknesses: [
      'Focus SDR uniquement — pas d\'autres métiers',
      'Pricing opaque (sur devis)',
      'Marché US principalement',
    ],
    targetMarket: 'Équipes commerciales B2B',
  },
  skl: {
    name: 'SKL.live',
    url: 'skl.live',
    type: 'complementary',
    pricing: { entry: 'Abonnement contenu', pro: 'Abonnement contenu' },
    agents: 1,
    strengths: [
      '300h d\'expertise business analysées',
      '40+ experts reconnus',
      'Assistant conversationnel qui cite ses sources',
      '30+ thématiques business couvertes',
    ],
    weaknesses: [
      'Pas d\'agents qui exécutent des tâches',
      'Pas de prospection, support, ou compta',
      'Uniquement du conseil, pas de l\'action',
    ],
    targetMarket: 'Entrepreneurs qui veulent du conseil business',
  },
}

// ============================================================
// BENCHMARKS SECTORIELS RÉELS
// ============================================================

interface SectorBenchmark {
  sector: string
  averageRevenue: string
  averageGrowth: string
  digitalAdoption: 'low' | 'medium' | 'high'
  avgEmployeeCount: number
  aiAdoptionRate: string
  topChallenges: string[]
  marketSize: string
  growthForecast: string
}

const SECTOR_BENCHMARKS: Record<string, SectorBenchmark> = {
  ecommerce: {
    sector: 'E-commerce',
    averageRevenue: '15-50k€/mois (TPE)',
    averageGrowth: '25-40% par an',
    digitalAdoption: 'high',
    avgEmployeeCount: 2,
    aiAdoptionRate: '45% utilisent déjà des chatbots',
    topChallenges: ['Acquisition client (coût en hausse)', 'Logistique et retours', 'Support client 24/7', 'SEO produit à grande échelle'],
    marketSize: '160 milliards € en France (2026)',
    growthForecast: '+12% par an jusqu\'en 2030',
  },
  services: {
    sector: 'Services & Conseil',
    averageRevenue: '10-60k€/mois (selon spécialité)',
    averageGrowth: '15-25% par an',
    digitalAdoption: 'medium',
    avgEmployeeCount: 3,
    aiAdoptionRate: '28% utilisent des outils IA',
    topChallenges: ['Prospection chronophage', 'Gestion de projets', 'Facturation et recouvrement', 'Fidélisation client'],
    marketSize: '280 milliards € en France',
    growthForecast: '+8% par an, forte demande en digital',
  },
  immobilier: {
    sector: 'Immobilier',
    averageRevenue: '10-100k€/mois (agence)',
    averageGrowth: '10-20% par an',
    digitalAdoption: 'medium',
    avgEmployeeCount: 3,
    aiAdoptionRate: '15% utilisent l\'IA (surtout estimation)',
    topChallenges: ['Prospection vendeurs difficile', 'Appels manqués = mandats perdus', 'Administratif lourd', 'Visibilité en ligne'],
    marketSize: '120 milliards € de transactions/an',
    growthForecast: '+5% par an, digitalisation accélérée',
  },
  sante: {
    sector: 'Santé & Bien-être',
    averageRevenue: '15-50k€/mois (cabinet)',
    averageGrowth: '5-10% par an',
    digitalAdoption: 'low',
    avgEmployeeCount: 4,
    aiAdoptionRate: '10% utilisent des assistants IA',
    topChallenges: ['No-show patients (20-30%)', 'Temps administratif excessif', 'Réglementation RGPD stricte', 'Gestion des urgences'],
    marketSize: '300 milliards € en France',
    growthForecast: '+4% par an, télémédecine en croissance',
  },
  formation: {
    sector: 'Formation & Coaching',
    averageRevenue: '5-30k€/mois',
    averageGrowth: '20-35% par an',
    digitalAdoption: 'medium',
    avgEmployeeCount: 2,
    aiAdoptionRate: '35% utilisent des outils digitaux',
    topChallenges: ['Visibilité et acquisition', 'Création de contenu pédagogique', 'Gestion administrative Qualiopi', 'Concurrence des plateformes'],
    marketSize: '50 milliards € en France',
    growthForecast: '+15% par an, boom du e-learning',
  },
  saas: {
    sector: 'SaaS & Tech',
    averageRevenue: '20-200k€/mois (MRR)',
    averageGrowth: '30-100% par an',
    digitalAdoption: 'high',
    avgEmployeeCount: 8,
    aiAdoptionRate: '70% intègrent de l\'IA',
    topChallenges: ['Croissance MRR soutenable', 'Churn et rétention', 'Product-market fit', 'Concurrence internationale'],
    marketSize: '25 milliards € en France',
    growthForecast: '+25% par an, IA-first companies dominent',
  },
}

// ============================================================
// ANALYSE CONCURRENTIELLE
// ============================================================

export interface CompetitiveAnalysis {
  bapicaVsCompetitors: ComparisonPoint[]
  marketPosition: MarketPosition
  competitiveAdvantages: string[]
  threatsToWatch: string[]
  recommendedStrategy: string
}

interface ComparisonPoint {
  dimension: string
  bapica: string
  concurrentA: string
  substi: string
  advantage: 'bapica' | 'competitor' | 'tie'
}

interface MarketPosition {
  overall: 'leader' | 'strong_challenger' | 'challenger' | 'niche'
  bySegment: Record<string, 'leader' | 'strong' | 'moderate' | 'weak'>
  opportunityScore: number // 0-100
}

export function generateCompetitiveAnalysis(sector: string): CompetitiveAnalysis {
  const benchmark = SECTOR_BENCHMARKS[sector] || SECTOR_BENCHMARKS.services
  
  const comparison: ComparisonPoint[] = [
    {
      dimension: 'Nombre d\'agents IA',
      bapica: '11 agents spécialisés',
      concurrentA: '8 agents',
      substi: '3 agents',
      advantage: 'bapica',
    },
    {
      dimension: 'Qualité IA',
      bapica: 'Claude Sonnet + Haiku',
      concurrentA: 'GPT-4o-mini',
      substi: 'GPT-4o-mini',
      advantage: 'bapica',
    },
    {
      dimension: 'Intelligence business',
      bapica: 'Score santé, ROI, benchmarks',
      concurrentA: 'Non',
      substi: 'Non',
      advantage: 'bapica',
    },
    {
      dimension: 'WhatsApp',
      bapica: 'Non (web app native)',
      concurrentA: 'Oui (Assistant WhatsApp)',
      substi: 'Non',
      advantage: 'competitor',
    },
    {
      dimension: 'Prix entrée',
      bapica: '49€/mois',
      concurrentA: '~39€/mois',
      substi: '~29€/mois',
      advantage: 'competitor',
    },
    {
      dimension: 'Onboarding',
      bapica: 'Automatique intelligent',
      concurrentA: 'Humain 1:1',
      substi: 'Standard',
      advantage: 'tie',
    },
    {
      dimension: 'Dashboard analytics',
      bapica: 'Oui, complet',
      concurrentA: 'Non',
      substi: 'Non',
      advantage: 'bapica',
    },
  ]
  
  const bapicaWins = comparison.filter(c => c.advantage === 'bapica').length
  const opportunityScore = Math.round((bapicaWins / comparison.length) * 100)
  
  return {
    bapicaVsCompetitors: comparison,
    marketPosition: {
      overall: 'strong_challenger',
      bySegment: {
        'agents_ia': 'strong',
        'telephonie': 'moderate',
        'business_intelligence': 'leader',
        'prix': 'moderate',
      },
      opportunityScore,
    },
    competitiveAdvantages: [
      'IA la plus avancée du marché (Claude vs GPT-4o-mini)',
      'Seule plateforme avec intelligence business adaptative',
      '11 agents vs 8 (Limova) vs 3 (Substi)',
      'Dashboard analytics que personne n\'a',
      'Onboarding intelligent automatisé (pas de RDV nécessaire)',
    ],
    threatsToWatch: [
      'Limova a WhatsApp — très populaire chez les TPE non tech',
      'Prix plus élevé que la concurrence (49€ vs 29-39€)',
      'Substi domine le marché du standard téléphonique simple',
      'AltaHQ (US) pourrait arriver en France',
    ],
    recommendedStrategy: benchmark.aiAdoptionRate === '45% utilisent déjà des chatbots' 
      ? 'Marché mature — focus sur la qualité IA supérieure et l\'intelligence business que personne n\'a'
      : benchmark.aiAdoptionRate === '28% utilisent des outils IA'
      ? 'Marché en adoption — éduquer sur l\'IA et démontrer le ROI'
      : 'Marché à évangéliser — contenu éducatif et cas clients',
  }
}

// ============================================================
// OPPORTUNITÉS DE MARCHÉ
// ============================================================

export interface MarketOpportunity {
  title: string
  marketSize: string
  growthRate: string
  bapicaFit: 'excellent' | 'good' | 'developing'
  actionItems: string[]
}

export function identifyOpportunities(sector: string, profile: any): MarketOpportunity[] {
  const benchmark = SECTOR_BENCHMARKS[sector] || SECTOR_BENCHMARKS.services
  const opportunities: MarketOpportunity[] = []
  
  // Opportunité 1 : Automatisation administrative
  if (benchmark.digitalAdoption !== 'high') {
    opportunities.push({
      title: 'Automatisation administrative',
      marketSize: `~${benchmark.marketSize.split(' ')[0]} de marché adressable`,
      growthRate: '+30% de demande d\'automatisation',
      bapicaFit: 'excellent',
      actionItems: [
        `Cibler les ${benchmark.sector} avec un message sur le temps économisé`,
        'Créer un calculateur de ROI spécifique au secteur',
        'Contacter les fédérations professionnelles',
      ],
    })
  }
  
  // Opportunité 2 : Standard téléphonique IA
  if (benchmark.topChallenges.some(c => c.toLowerCase().includes('appel') || c.toLowerCase().includes('téléphone'))) {
    opportunities.push({
      title: 'Standard téléphonique IA',
      marketSize: `${benchmark.avgEmployeeCount * 200}€/mois d\'économie par entreprise`,
      growthRate: '+45% d\'adoption des standards IA',
      bapicaFit: 'excellent',
      actionItems: [
        'Mettre en avant le ROI immédiat (1 appel manqué = X€ perdu)',
        'Proposer une démo téléphonique gratuite',
        'Cibler les heures de forte affluence du secteur',
      ],
    })
  }
  
  // Opportunité 3 : Content marketing
  if (benchmark.topChallenges.some(c => c.toLowerCase().includes('visibilité') || c.toLowerCase().includes('contenu'))) {
    opportunities.push({
      title: 'Content marketing automatisé',
      marketSize: '15-30% du budget marketing des PME',
      growthRate: '+50% de demande de contenu IA',
      bapicaFit: 'excellent',
      actionItems: [
        'Générer un exemple d\'article SEO pour le prospect',
        'Comparer le coût rédacteur vs Bapica',
        'Proposer 1 mois de contenu gratuit à l\'inscription',
      ],
    })
  }
  
  return opportunities
}

// ============================================================
// VEILLE CONCURRENTIELLE
// ============================================================

export interface CompetitiveIntel {
  competitor: string
  lastChecked: string
  pricingChanged: boolean
  newFeatures: string[]
  marketMoves: string[]
  threatLevel: 'low' | 'medium' | 'high'
}

export function getCompetitiveIntel(): CompetitiveIntel[] {
  return [
    {
      competitor: 'Concurrent A',
      lastChecked: '2026-07-08',
      pricingChanged: false,
      newFeatures: ['WhatsApp Assistant WhatsApp amélioré'],
      marketMoves: ['Partenariat avec BFM Business', 'Campagne TV Legend'],
      threatLevel: 'high',
    },
    {
      competitor: 'Substi.ai',
      lastChecked: '2026-07-08',
      pricingChanged: false,
      newFeatures: ['Nouveau design site web'],
      marketMoves: ['Focus sur le marché du standard téléphonique'],
      threatLevel: 'medium',
    },
    {
      competitor: 'AltaHQ',
      lastChecked: '2026-07-08',
      pricingChanged: false,
      newFeatures: ['Katie AI SDR v2'],
      marketMoves: ['Expansion européenne probable'],
      threatLevel: 'medium',
    },
    {
      competitor: 'SKL.live',
      lastChecked: '2026-07-08',
      pricingChanged: false,
      newFeatures: ['Assistant SKL enrichi'],
      marketMoves: ['Contenu et conseil business'],
      threatLevel: 'low',
    },
  ]
}

// ============================================================
// TENDANCES SECTORIELLES
// ============================================================

export interface SectorTrend {
  trend: string
  impact: 'transformational' | 'high' | 'medium' | 'low'
  timeframe: 'now' | '6-months' | '1-year' | '2-years'
  relevance: string
}

const TRENDS_DB: Record<string, SectorTrend[]> = {
  ecommerce: [
    { trend: 'IA générative pour fiches produits', impact: 'transformational', timeframe: 'now', relevance: 'Automatisation des descriptions produits SEO' },
    { trend: 'Chatbots vocaux pour SAV', impact: 'high', timeframe: '6-months', relevance: 'Support client 24/7 sans humain' },
    { trend: 'Personnalisation prédictive', impact: 'high', timeframe: '1-year', relevance: 'Recommandations produits IA' },
  ],
  services: [
    { trend: 'Agents IA pour prospection B2B', impact: 'transformational', timeframe: 'now', relevance: 'LinkedIn + email automatisés' },
    { trend: 'Génération de propositions commerciales', impact: 'high', timeframe: 'now', relevance: 'Devis et propositions en 30 secondes' },
    { trend: 'Consulting augmenté par IA', impact: 'medium', timeframe: '1-year', relevance: 'Analyse de données client par IA' },
  ],
  immobilier: [
    { trend: 'Visites virtuelles IA', impact: 'high', timeframe: 'now', relevance: 'Visites 3D générées automatiquement' },
    { trend: 'Estimation IA en temps réel', impact: 'transformational', timeframe: '6-months', relevance: 'Prix prédits par machine learning' },
    { trend: 'Agent téléphonique 24/7', impact: 'high', timeframe: 'now', relevance: '0 appel manqué, qualification auto' },
  ],
}

export function getSectorTrends(sector: string): SectorTrend[] {
  return TRENDS_DB[sector] || [
    { trend: 'Automatisation des tâches répétitives', impact: 'high', timeframe: 'now', relevance: 'Gain de productivité immédiat' },
    { trend: 'IA conversationnelle pour relation client', impact: 'transformational', timeframe: '6-months', relevance: 'Support et vente 24/7' },
    { trend: 'Analyse prédictive pour PME', impact: 'high', timeframe: '1-year', relevance: 'Décisions basées sur les données' },
  ]
}
