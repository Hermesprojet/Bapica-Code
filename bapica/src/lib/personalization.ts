// Moteur de personnalisation intelligent
// Analyse les réponses onboarding pour adapter l'expérience client

// Une application connectée par le client lors de l'onboarding
export interface ConnectedApp {
  name: string
  url?: string
}

export interface OnboardingData {
  activity?: string
  activityOther?: string
  adminTasks?: string[]
  adminTasksOther?: string
  contactMethods?: string[]
  contactMethodsOther?: string
  apps?: ConnectedApp[]
  appsOther?: string
  businessDescription?: string
  objectives?: string[]
  objectivesOther?: string
}

// Vérifie si l'une des applications connectées correspond à un mot-clé
// (ex: 'shopify', 'wordpress', 'google'). Comparaison insensible à la casse.
function appsInclude(apps: ConnectedApp[], keyword: string): boolean {
  const needle = keyword.toLowerCase()
  return apps.some((app) => (app?.name || '').toLowerCase().includes(needle))
}

// Étapes de configuration recommandées après onboarding
export interface SetupStep {
  key: string
  label: string
  done: boolean
  href: string
}

// Suggère les prochaines actions selon le profil du client
export function getSetupSteps(onboarding: OnboardingData | null): SetupStep[] {
  const steps: SetupStep[] = [
    { key: 'onboarding', label: 'Questionnaire complété', done: !!onboarding, href: '/onboarding' },
    { key: 'agents', label: 'Découvrir vos agents', done: false, href: '/dashboard/agents' },
  ]

  if (!onboarding) return steps

  const contact = onboarding.contactMethods || []
  const tasks = onboarding.adminTasks || []
  const apps = onboarding.apps || []

  // Si le client utilise le téléphone → suggérer d'activer l'agent téléphonique
  if (contact.includes('telephone')) {
    steps.push({
      key: 'phone-agent',
      label: 'Activer l\'Agent Téléphonique',
      done: false,
      href: '/dashboard/agents/telephone',
    })
  }

  // Si WhatsApp → suggérer connexion WhatsApp
  if (contact.includes('whatsapp')) {
    steps.push({
      key: 'whatsapp',
      label: 'Connecter WhatsApp Business',
      done: false,
      href: '/dashboard/settings',
    })
  }

  // Si tâches comptables → suggérer l'agent Comptabilité
  if (tasks.includes('comptabilite') || tasks.includes('factures')) {
    steps.push({
      key: 'accounting',
      label: 'Configurer l\'Agent Comptable',
      done: false,
      href: '/dashboard/agents/accounting',
    })
  }

  // Si tâches juridiques → suggérer l'agent Juridique
  if (tasks.includes('juridique')) {
    steps.push({
      key: 'legal',
      label: 'Configurer l\'Agent Juridique',
      done: false,
      href: '/dashboard/agents/legal',
    })
  }

  // Si Google Agenda → suggérer connexion
  if (appsInclude(apps, 'google')) {
    steps.push({
      key: 'calendar',
      label: 'Connecter Google Agenda',
      done: false,
      href: '/dashboard/settings',
    })
  }

  return steps
}

// Widgets intelligents recommandés selon le profil
export interface SmartWidget {
  id: string
  title: string
  description: string
  cta: string
  href: string
  priority: number
}

export function getRecommendedWidgets(onboarding: OnboardingData | null): SmartWidget[] {
  const widgets: SmartWidget[] = []
  if (!onboarding) return widgets

  const contact = onboarding.contactMethods || []
  const tasks = onboarding.adminTasks || []
  const apps = onboarding.apps || []

  // Widget appel téléphonique
  if (contact.includes('telephone')) {
    widgets.push({
      id: 'phone',
      title: 'Vos clients vous appellent 📞',
      description: 'Activez l\'Agent Téléphonique pour répondre 24/7 et ne rater aucun appel.',
      cta: 'Activer',
      href: '/dashboard/agents/telephone',
      priority: 10,
    })
  }

  // Widget prospection LinkedIn
  if (contact.includes('linkedin')) {
    widgets.push({
      id: 'linkedin',
      title: 'Prospection LinkedIn 🔗',
      description: 'Laissez Elio prospecter et qualifier des leads pour vous sur LinkedIn.',
      cta: 'Configurer',
      href: '/dashboard/agents/prospection-strategie',
      priority: 8,
    })
  }

  // Widget comptabilité
  if (tasks.includes('comptabilite') || tasks.includes('factures')) {
    widgets.push({
      id: 'accounting',
      title: 'Comptabilité simplifiée 🧮',
      description: 'Automatisez vos factures, relances et tableaux de bord financiers.',
      cta: 'Activer',
      href: '/dashboard/agents/accounting',
      priority: 9,
    })
  }

  // Widget SEO
  if (onboarding.activity === 'ecommerce' || appsInclude(apps, 'shopify') || appsInclude(apps, 'wordpress')) {
    widgets.push({
      id: 'seo',
      title: 'Boostez votre SEO 📈',
      description: 'Lou peut rédiger et publier des articles optimisés SEO automatiquement.',
      cta: 'Découvrir',
      href: '/dashboard/agents/content',
      priority: 7,
    })
  }

  // Widget recrutement
  if (tasks.includes('paie')) {
    widgets.push({
      id: 'recruitment',
      title: 'Vous recrutez ? 👥',
      description: 'Yanis peut trier les CV et présélectionner les meilleurs candidats.',
      cta: 'Configurer',
      href: '/dashboard/agents/recruiter',
      priority: 6,
    })
  }

  // Suggestion d'intégration
  if (!appsInclude(apps, 'google') && contact.includes('email')) {
    widgets.push({
      id: 'google-workspace',
      title: 'Connectez Google Workspace 🔌',
      description: 'Synchronisez votre email, agenda et documents avec vos agents IA.',
      cta: 'Connecter',
      href: '/dashboard/settings',
      priority: 5,
    })
  }

  return widgets.sort((a, b) => b.priority - a.priority)
}

// Suggère les agents les plus pertinents pour un profil
export function getRecommendedAgentIds(onboarding: OnboardingData | null): string[] {
  if (!onboarding) return ['general']
  
  const ids: string[] = ['general'] // toujours l'agent général
  const contact = onboarding.contactMethods || []
  const tasks = onboarding.adminTasks || []
  const apps = onboarding.apps || []

  if (contact.includes('telephone')) ids.push('telephone')
  if (contact.includes('whatsapp') || contact.includes('chat')) ids.push('support')
  if (contact.includes('linkedin')) ids.push('prospection-strategie')
  if (tasks.includes('comptabilite') || tasks.includes('factures')) ids.push('accounting')
  if (tasks.includes('juridique')) ids.push('legal')
  if (tasks.includes('paie')) ids.push('recruiter')
  if (appsInclude(apps, 'shopify') || appsInclude(apps, 'wordpress')) ids.push('content')
  if (onboarding.activity === 'ecommerce') ids.push('content')

  return [...new Set(ids)] // déduplication
}
