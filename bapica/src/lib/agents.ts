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

const AGENTS: AgentConfig[] = [
  {
    id: 'general',
    name: 'Agent Général',
    persona: 'Léo',
    description: "Orchestrateur et point d'entrée unique : connaît votre entreprise, gère votre to-do, diagnostique vos leviers de croissance, coordonne les autres agents et exécute vos missions — même par WhatsApp.",
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
    description: "Trie et répond aux emails et messages, garde l'historique client, escalade si c'est complexe.",
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
    description: 'Audit SEO (votre site et ceux des concurrents), articles optimisés, calendrier éditorial, publication sur CMS et réseaux sociaux.',
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
    description: 'Campagnes LinkedIn/phoning, qualification de leads, prise de RDV, posts et publication multi-plateformes.',
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
    description: "Appels de qualification et closing, argumentaires sur mesure, traitement d'objections, résumé après chaque appel. Trouve aussi les coordonnées des prospects sur les plateformes dédiées.",
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
    description: 'Standard 24/7 (téléphone, WhatsApp, web) : qualification, prise de RDV, comptes rendus par mail.',
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
    description: "Facturation, relances d'impayés, prévisions de trésorerie, budgets et rapports financiers.",
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
    description: 'Stratégie réseaux, visuels et vidéos IA (même à partir de photos produit), publication programmée multi-réseaux.',
    model: 'claude-haiku-4',
    temperature: 0.7,
    maxTokens: 3000,
    // ─── Génération visuelle (Alexya-compatible) — 4 modes ──────────
    minPlan: 'essential',
    icon: 'Video',
    tools: ['heygen', 'runway', 'elevenlabs'],
    teamRole: 'specialist',
    color: 'purple',
    hidden: false,
    avatar: { from: '#8b5cf6', to: '#7c3aed', skin: '#c68642', hair: 'long', hairColor: '#1a1a1a', accessory: 'none' },
  },
  {
    id: 'recruiter',
    name: 'Recruteur IA',
    persona: 'Yanis',
    description: "Offres de poste, tri intelligent des CV, préparation d'entretiens, documents RH et intégration.",
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
    description: 'Rédaction (contrats, CGV, RGPD), analyse de contrats reçus, mises en demeure, conformité RGPD.',
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
  telephone: 'telephone',
  vocal: 'closer', // « vocal » → Nadia, le closer vocal
}

export function getAgentById(id: string): AgentConfig | undefined {
  const resolvedId = AGENT_ALIASES[id] || id
  return AGENTS.find((a) => a.id === resolvedId)
}

export default AGENTS
