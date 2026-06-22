export type PlanKey = 'starter' | 'pro' | 'business'

export interface AgentConfig {
  id: string
  name: string
  description: string
  model: string
  temperature: number
  maxTokens: number
  minPlan: PlanKey
  icon: string
  tools: string[]
  color?: string
}

const AGENTS: AgentConfig[] = [
  {
    id: 'general',
    name: 'Agent Général',
    description: 'Point d\'entrée universel. Posez n\'importe quelle question.',
    model: 'claude-sonnet-4',
    temperature: 0.6,
    maxTokens: 3000,
    minPlan: 'starter',
    icon: 'Bot',
    tools: ['claude_api', 'openai'],
  },
  {
    id: 'support',
    name: 'Support Client',
    description: 'Support 24/7 multilingue. Répond aux questions, résout les problèmes.',
    model: 'claude-sonnet-4',
    temperature: 0.3,
    maxTokens: 2000,
    minPlan: 'starter',
    icon: 'HeadphonesIcon',
    tools: ['crisp', 'intercom', 'whatsapp_api'],
  },
  {
    id: 'content',
    name: 'Créateur de Contenu',
    description: 'Articles SEO, posts réseaux, newsletters, scripts vidéo.',
    model: 'claude-sonnet-4',
    temperature: 0.7,
    maxTokens: 3000,
    minPlan: 'starter',
    icon: 'FileText',
    tools: ['claude_api', 'wordpress', 'buffer'],
  },
  {
    id: 'prospector',
    name: 'Prospecteur Commercial',
    description: 'Identifie et qualifie des leads B2B, messages personnalisés.',
    model: 'claude-sonnet-4',
    temperature: 0.4,
    maxTokens: 2000,
    minPlan: 'pro',
    icon: 'Users',
    tools: ['apollo_io', 'linkedin_sales_navigator'],
  },
  {
    id: 'closer',
    name: 'Closer Vocal',
    description: 'Qualifie par téléphone, traite les objections, convertit en RDV.',
    model: 'claude-sonnet-4',
    temperature: 0.5,
    maxTokens: 2000,
    minPlan: 'pro',
    icon: 'Phone',
    tools: ['vapi', 'cal_com'],
  },
  {
    id: 'telephone',
    name: 'Agent Téléphonique',
    description: 'Standard virtuel intelligent, routage, prise de messages.',
    model: 'claude-sonnet-4',
    temperature: 0.4,
    maxTokens: 1500,
    minPlan: 'pro',
    icon: 'Building2',
    tools: ['vapi', 'twilio', 'elevenlabs'],
  },
  {
    id: 'accounting',
    name: 'Agent Comptabilité',
    description: 'Factures, relances impayés, TVA, tableau de bord financier.',
    model: 'claude-sonnet-4',
    temperature: 0.2,
    maxTokens: 3000,
    minPlan: 'pro',
    icon: 'Calculator',
    tools: ['stripe', 'pennylane', 'qonto'],
  },
  {
    id: 'video',
    name: 'Créateur Vidéo IA',
    description: 'Vidéos promotionnelles, Reels, avatars IA multilingues.',
    model: 'claude-sonnet-4',
    temperature: 0.7,
    maxTokens: 3000,
    minPlan: 'business',
    icon: 'Video',
    tools: ['heygen', 'runway', 'elevenlabs'],
  },
  {
    id: 'recruiter',
    name: 'Recruteur IA',
    description: 'Rédaction d\'offres, tri CV, présélection vocale.',
    model: 'claude-sonnet-4',
    temperature: 0.3,
    maxTokens: 3000,
    minPlan: 'business',
    icon: 'Search',
    tools: ['vapi', 'linkedin', 'cal_com'],
  },
  {
    id: 'legal',
    name: 'Administratif & Juridique',
    description: 'Contrats, CGV, RGPD, mentions légales, analyse documents.',
    model: 'claude-sonnet-4',
    temperature: 0.3,
    maxTokens: 4000,
    minPlan: 'business',
    icon: 'FileCheck',
    tools: ['claude_api', 'notion', 'docusign'],
  },
  {
    id: 'analytics',
    name: 'Analytics & Reporting',
    description: 'Dashboards, tendances, prédictions, recommandations data.',
    model: 'claude-sonnet-4',
    temperature: 0.3,
    maxTokens: 3000,
    minPlan: 'business',
    icon: 'BarChart3',
    tools: ['supabase', 'google_analytics_4', 'n8n'],
    color: 'from-teal-500 to-teal-600',
  },
  {
    id: 'trends',
    name: 'Analyse des Tendances Google',
    description: 'Surveille Google Trends, identifie les opportunités business émergentes.',
    model: 'claude-sonnet-4',
    temperature: 0.3,
    maxTokens: 3000,
    minPlan: 'business',
    icon: 'TrendingUp',
    tools: ['google_trends', 'pytrends', 'web_search', 'serpapi'],
    color: 'from-lime-500 to-lime-600',
  },
]

export function getAgentsForPlan(plan: PlanKey): AgentConfig[] {
  const planLevel: Record<PlanKey, number> = {
    starter: 0,
    pro: 1,
    business: 2,
  }
  const userLevel = planLevel[plan] ?? 0
  return AGENTS.filter((a) => planLevel[a.minPlan] <= userLevel)
}

export function getAgentById(id: string): AgentConfig | undefined {
  return AGENTS.find((a) => a.id === id)
}

export default AGENTS
