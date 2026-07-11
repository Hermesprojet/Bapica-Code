export type PlanKey = 'essential' | 'pro'

export type AvatarHair = 'short' | 'long' | 'bun' | 'curly' | 'buzz' | 'bald'
export type AvatarAccessory = 'none' | 'glasses' | 'headset' | 'cap'

export interface AgentAvatar {
  from: string
  to: string
  skin: string
  hair: AvatarHair
  hairColor: string
  accessory: AvatarAccessory
}

export interface AgentConfig {
  id: string
  name: string
  persona: string
  description: string
  model: string
  temperature: number
  maxTokens: number
  minPlan: PlanKey
  icon: string
  tools: string[]
  teamRole?: 'coordinator' | 'specialist' | 'analyst'
  color?: string
  hidden?: boolean // Agent retiré de la vitrine publique
  avatar: AgentAvatar
}

export const GROWTH_ADVISOR_PROMPT = `Tu es un conseiller commercial et stratégique senior pour PME. Ton rôle combine prospection opérationnelle et conseil stratégique CA.

1. PROSPECTION OPÉRATIONNELLE
- Identifier des cibles clients pertinentes (secteur, taille, besoin)
- Rédiger des messages de prospection (email, LinkedIn, appel à froid)
- Construire des séquences de relance
- Qualifier les leads (BANT ou méthode adaptée)

2. CONSEIL STRATÉGIQUE CA
- Analyser le business (offre, positionnement, marché)
- Proposer des leviers concrets d'augmentation du CA (upsell, cross-sell, nouveaux segments, pricing, rétention)
- Prioriser les actions par rapport effort/impact
- Poser des questions de clarification si le contexte business manque

RÈGLES :
- Toujours demander le secteur, la taille et l'objectif si pas déjà connu
- Réponses actionnables, pas de généralités
- Structurer les réponses longues en étapes
- Ne jamais inventer de chiffres : dire "à vérifier" si incertain`;

const AGENTS: AgentConfig[] = [
  {
    id: 'general',
    name: 'Agent Général',
    persona: 'Léo',
    description: "Point d'entrée universel. Posez n'importe quelle question.",
    model: 'claude-haiku-4',
    temperature: 0.6,
    maxTokens: 1500,
    minPlan: 'essential',
    icon: 'Bot',
    tools: ['claude_api', 'openai'],
    teamRole: 'coordinator',
    color: 'from-blue-500 to-blue-600',
    avatar: { from: '#3b82f6', to: '#2563eb', skin: '#f1c9a5', hair: 'short', hairColor: '#4a3526', accessory: 'glasses' },
  },
  {
    id: 'support',
    name: 'Support Client',
    persona: 'Sofia',
    description: "Support 24/7 multilingue. Répond aux questions, résout les problèmes.",
    model: 'claude-haiku-4',
    temperature: 0.3,
    maxTokens: 1500,
    minPlan: 'essential',
    icon: 'HeadphonesIcon',
    tools: ['crisp', 'intercom', 'whatsapp_api'],
    teamRole: 'specialist',
    color: 'from-emerald-500 to-emerald-600',
    avatar: { from: '#10b981', to: '#059669', skin: '#eab891', hair: 'long', hairColor: '#2d2d2d', accessory: 'headset' },
  },
  {
    id: 'content',
    name: 'Créateur de Contenu',
    persona: 'Camille',
    description: 'Articles SEO, posts réseaux, newsletters, scripts vidéo.',
    model: 'claude-haiku-4',
    temperature: 0.7,
    maxTokens: 2000,
    minPlan: 'essential',
    icon: 'FileText',
    tools: ['claude_api', 'wordpress', 'buffer'],
    teamRole: 'specialist',
    color: 'from-violet-500 to-violet-600',
    avatar: { from: '#8b5cf6', to: '#7c3aed', skin: '#f8d5b8', hair: 'curly', hairColor: '#6b4423', accessory: 'none' },
  },
  {
    id: 'prospection-strategie',
    name: 'Conseiller Croissance & Prospection',
    persona: 'Marc',
    description: 'Prospecte de nouveaux clients et te conseille pour augmenter ton CA.',
    model: 'claude-sonnet-4',
    temperature: 0.5,
    maxTokens: 3000,
    minPlan: 'essential',
    icon: 'TrendingUp',
    tools: ['apollo_io', 'linkedin_sales_navigator', 'market_intelligence', 'business_analysis'],
    teamRole: 'specialist',
    color: 'from-emerald-500 to-teal-500',
    avatar: { from: '#10b981', to: '#0d9488', skin: '#f8d5b8', hair: 'buzz', hairColor: '#1a1a1a', accessory: 'glasses' },
  },
  {
    id: 'closer',
    name: 'Closer Vocal',
    persona: 'Nadia',
    description: 'Qualifie par téléphone, traite les objections, convertit en RDV.',
    model: 'claude-haiku-4',
    temperature: 0.5,
    maxTokens: 2000,
    minPlan: 'essential',
    icon: 'Phone',
    tools: ['vapi', 'cal_com'],
    teamRole: 'specialist',
    color: 'from-rose-500 to-rose-600',
    avatar: { from: '#f43f5e', to: '#e11d48', skin: '#eab891', hair: 'bun', hairColor: '#1a1a1a', accessory: 'headset' },
  },
  {
    id: 'telephone',
    name: 'Agent Téléphonique',
    persona: 'Hugo',
    description: 'Standard virtuel intelligent, routage, prise de messages.',
    model: 'claude-haiku-4',
    temperature: 0.4,
    maxTokens: 1000,
    minPlan: 'pro',
    icon: 'Building2',
    tools: ['vapi', 'twilio', 'elevenlabs'],
    teamRole: 'specialist',
    color: 'from-cyan-500 to-cyan-600',
    avatar: { from: '#06b6d4', to: '#0891b2', skin: '#f1c9a5', hair: 'buzz', hairColor: '#3a3a3a', accessory: 'headset' },
  },
  {
    id: 'accounting',
    name: 'Agent Comptabilité',
    persona: 'Claire',
    description: 'Factures, relances impayés, TVA, tableau de bord financier.',
    model: 'claude-sonnet-4',
    temperature: 0.2,
    maxTokens: 3000,
    minPlan: 'pro',
    icon: 'Calculator',
    tools: ['stripe', 'pennylane', 'qonto'],
    teamRole: 'analyst',
    color: 'from-amber-500 to-amber-600',
    avatar: { from: '#f59e0b', to: '#d97706', skin: '#f8d5b8', hair: 'bun', hairColor: '#6b4423', accessory: 'glasses' },
  },
  {
    id: 'video',
    name: 'Créateur Vidéo IA',
    persona: 'Maya',
    description: 'Vidéos promotionnelles, Reels, avatars IA multilingues.',
    model: 'claude-haiku-4',
    temperature: 0.7,
    maxTokens: 3000,
    minPlan: 'pro',
    icon: 'Video',
    tools: ['heygen', 'runway', 'elevenlabs'],
    teamRole: 'specialist',
    hidden: true,
    color: 'from-pink-500 to-pink-600',
    avatar: { from: '#ec4899', to: '#db2777', skin: '#c68642', hair: 'long', hairColor: '#1a1a1a', accessory: 'none' },
  },
  {
    id: 'recruiter',
    name: 'Recruteur IA',
    persona: 'Yanis',
    description: "Rédaction d'offres, tri CV, présélection vocale.",
    model: 'claude-haiku-4',
    temperature: 0.3,
    maxTokens: 2000,
    minPlan: 'essential',
    icon: 'Search',
    tools: ['vapi', 'linkedin', 'cal_com'],
    teamRole: 'specialist',
    color: 'from-indigo-500 to-indigo-600',
    avatar: { from: '#6366f1', to: '#4f46e5', skin: '#d99a6c', hair: 'short', hairColor: '#2b2b2b', accessory: 'glasses' },
  },
  {
    id: 'legal',
    name: 'Administratif & Juridique',
    persona: 'Inès',
    description: 'Contrats, CGV, RGPD, mentions légales, analyse documents.',
    model: 'claude-haiku-4',
    temperature: 0.3,
    maxTokens: 3000,
    minPlan: 'essential',
    icon: 'FileCheck',
    tools: ['claude_api', 'notion', 'docusign'],
    teamRole: 'specialist',
    color: 'from-slate-500 to-slate-600',
    avatar: { from: '#64748b', to: '#475569', skin: '#eab891', hair: 'long', hairColor: '#4a3526', accessory: 'glasses' },
  },
  {
    id: 'analytics',
    name: 'Analytics & Reporting',
    persona: 'Tom',
    description: 'Dashboards, tendances, prédictions, recommandations data.',
    model: 'claude-sonnet-4',
    temperature: 0.3,
    maxTokens: 3000,
    minPlan: 'pro',
    icon: 'BarChart3',
    tools: ['supabase', 'google_analytics_4', 'n8n'],
    teamRole: 'analyst',
    color: 'from-teal-500 to-teal-600',
    avatar: { from: '#14b8a6', to: '#0d9488', skin: '#f1c9a5', hair: 'short', hairColor: '#caa472', accessory: 'glasses' },
  },
  {
    id: 'trends',
    name: 'Analyse des Tendances Google',
    persona: 'Lina',
    description: 'Surveille Google Trends, identifie les opportunités business émergentes.',
    model: 'claude-haiku-4',
    temperature: 0.3,
    maxTokens: 1500,
    minPlan: 'essential',
    icon: 'TrendingUp',
    tools: ['google_trends', 'pytrends', 'web_search', 'serpapi'],
    teamRole: 'analyst',
    color: 'from-lime-500 to-lime-600',
    avatar: { from: '#84cc16', to: '#65a30d', skin: '#d99a6c', hair: 'curly', hairColor: '#2b2b2b', accessory: 'none' },
  },
  {
    id: 'scaling',
    name: 'Agent Croissance & Scaling',
    persona: 'Roxane',
    description: "Stratégie de croissance : diagnostic de scalabilité, optimisation des processus, levée de fonds, recrutement, expansion marché.",
    model: 'claude-sonnet-4',
    temperature: 0.4,
    maxTokens: 3000,
    minPlan: 'pro',
    icon: 'TrendingUp',
    tools: ['stripe', 'google_analytics', 'hubspot', 'notion'],
    teamRole: 'analyst',
    color: 'from-purple-500 to-violet-600',
    avatar: { from: '#8b5cf6', to: '#7c3aed', skin: '#f8d5b8', hair: 'long', hairColor: '#4a3526', accessory: 'glasses' },
  },
]

export function getAgentsForPlan(plan: PlanKey): AgentConfig[] {
  const planLevel: Record<PlanKey, number> = {
    essential: 0,
    pro: 1,
  }
  const userLevel = planLevel[plan] ?? 0
  return AGENTS.filter((a) => planLevel[a.minPlan] <= userLevel && !a.hidden)
}

// Alias pour compatibilité avec différentes conventions de nommage
const AGENT_ALIASES: Record<string, string> = {
  juridique: 'legal',
  compta: 'accounting',
  comptabilite: 'accounting',
  recrutement: 'recruiter',
  tendances: 'trends',
  telephone: 'telephone',
  vocal: 'video', // fallback
}

export function getAgentById(id: string): AgentConfig | undefined {
  const resolvedId = AGENT_ALIASES[id] || id
  return AGENTS.find((a) => a.id === resolvedId)
}

export default AGENTS
