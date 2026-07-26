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
    description: "Orchestrateur et point d'entrée : connaît votre entreprise, se branche à vos emails et votre agenda, produit vos documents (devis PDF, Excel, PowerPoint), analyse vos fichiers, coordonne les autres agents et exécute vos missions — même par WhatsApp.",
    model: 'claude-haiku-4',
    temperature: 0.6,
    maxTokens: 2500,
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
    description: "Répond aux clients 24/7 (chat, WhatsApp, email) à partir de votre base de connaissance, garde l'historique, étiquette et escalade si c'est complexe.",
    model: 'claude-haiku-4',
    temperature: 0.3,
    maxTokens: 2000,
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
    description: 'Plan de contenu mensuel, audit SEO (votre site et vos concurrents), articles optimisés, posts adaptés à chaque réseau, publication sur CMS (WordPress, Wix, Shopify) et réseaux sociaux.',
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
    description: "Campagnes LinkedIn et d'appels sortants, analyse de prospects, qualification et étiquetage des leads, prise de RDV, diagnostic commercial chiffré, préparation des RDV clés, et intelligence concurrentielle (concurrents locaux et en ligne, tableau comparatif, battlecard, veille de marché récurrente).",
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
    description: "Appels de qualification et closing, argumentaires sur mesure, traitement d'objections, étiquetage et résumé après chaque appel, RDV placé dans l'agenda. Trouve aussi les coordonnées des prospects sur les plateformes dédiées.",
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
    description: 'Standard 24/7 (téléphone, WhatsApp, web) : répond dès la 1ʳᵉ sonnerie, qualifie, étiquette, prend les RDV et envoie un compte rendu par mail ou SMS, à partir de votre base de connaissance.',
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
    description: "Facturation (Pennylane, Axonaut, Odoo), relances d'impayés, alertes de trésorerie et d'échéances (TVA, URSSAF), rentabilité par client, prévisions 3/6/12 mois, budgets, rapports et récap pour l'expert-comptable.",
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
    description: 'Stratégie réseaux, visuels haute résolution (jusqu\'en 4K) et vidéos IA ultra-réalistes (à partir d\'un texte ou de vos photos), publication programmée multi-réseaux.',
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
    description: "Offres par plateforme, tri intelligent des CV, préparation d'entretiens, contrats de travail et documents RH, plan d'intégration, grille de salaire et suivi des collaborateurs.",
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
    description: "Rédaction (contrats, NDA, pactes d'associés, CGV, RGPD), analyse de contrats reçus et reformulations, mises en demeure, conseil en droit des sociétés et du travail, veille juridique.",
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
    name: 'Analyste de Données',
    persona: 'Théo',
    description: "Transforme vos données (fichiers Excel/CSV, banque et plateformes connectées) en décisions : KPI, tableaux et tendances, détection d'anomalies, rapports PDF/Excel clairs et recommandations concrètes.",
    model: 'claude-haiku-4',
    temperature: 0.2,
    maxTokens: 3000,
    minPlan: 'essential',
    icon: 'BarChart3',
    tools: ['claude_api', 'excel', 'analytics'],
    teamRole: 'analyst',
    color: 'from-cyan-500 to-cyan-600',
    avatar: { from: '#06b6d4', to: '#0891b2', skin: '#e8b88f', hair: 'short', hairColor: '#2b2b2b', accessory: 'glasses' },
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
