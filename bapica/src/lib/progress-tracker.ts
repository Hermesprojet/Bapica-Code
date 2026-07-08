/**
 * Système de progression et milestones pour chaque entreprise
 * Suit l'évolution du profil business dans le temps
 */

export interface Milestone {
  id: string
  title: string
  description: string
  category: 'onboarding' | 'activation' | 'growth' | 'optimization'
  status: 'locked' | 'available' | 'in_progress' | 'completed'
  impact: 'low' | 'medium' | 'high' | 'transformational'
  agentInvolved?: string
  estimatedTimeToComplete?: string
  completedAt?: string
}

export interface ProgressTracker {
  overallProgress: number  // 0-100
  stage: string
  completedMilestones: number
  totalMilestones: number
  nextMilestone?: Milestone
  recentAchievements: string[]
  streak: number  // jours consécutifs d'activité
  lastActivity?: string
}

const MILESTONE_TEMPLATES: Record<string, Milestone[]> = {
  onboarding: [
    {
      id: 'complete-profile',
      title: 'Compléter votre profil business',
      description: 'Ajoutez votre secteur, taille, objectifs et outils utilisés',
      category: 'onboarding',
      status: 'available',
      impact: 'high',
      estimatedTimeToComplete: '5 minutes',
    },
    {
      id: 'activate-first-agent',
      title: 'Activer votre premier agent IA',
      description: 'Choisissez l\'agent le plus impactant pour votre activité',
      category: 'onboarding',
      status: 'locked',
      impact: 'transformational',
      estimatedTimeToComplete: '2 minutes',
    },
    {
      id: 'connect-tools',
      title: 'Connecter vos outils',
      description: 'Liez votre CRM, email et calendrier à Bapica',
      category: 'onboarding',
      status: 'locked',
      impact: 'high',
      estimatedTimeToComplete: '10 minutes',
    },
  ],
  activation: [
    {
      id: 'first-agent-task',
      title: 'Lancer votre première tâche automatisée',
      description: 'Demandez à un agent d\'exécuter une tâche réelle',
      category: 'activation',
      status: 'locked',
      impact: 'transformational',
      estimatedTimeToComplete: '5 minutes',
    },
    {
      id: 'first-saved-time',
      title: 'Économiser votre première heure',
      description: 'Mesurez le temps gagné grâce à l\'automatisation',
      category: 'activation',
      status: 'locked',
      impact: 'high',
      estimatedTimeToComplete: '1-3 jours',
    },
    {
      id: 'invite-team',
      title: 'Inviter votre équipe',
      description: 'Partagez l\'accès avec vos collaborateurs',
      category: 'activation',
      status: 'locked',
      impact: 'medium',
      estimatedTimeToComplete: '2 minutes',
    },
  ],
  growth: [
    {
      id: 'scale-agents',
      title: 'Activer 3 agents ou plus',
      description: 'Déployez plusieurs agents pour couvrir tous vos besoins',
      category: 'growth',
      status: 'locked',
      impact: 'transformational',
      estimatedTimeToComplete: '1-2 semaines',
    },
    {
      id: 'automate-workflow',
      title: 'Automatiser un workflow complet',
      description: 'Créez une chaîne d\'automatisation de bout en bout',
      category: 'growth',
      status: 'locked',
      impact: 'transformational',
      estimatedTimeToComplete: '1 semaine',
    },
    {
      id: 'roi-positive',
      title: 'Atteindre un ROI positif',
      description: 'Les économies dépassent le coût de l\'abonnement',
      category: 'growth',
      status: 'locked',
      impact: 'high',
      estimatedTimeToComplete: '1 mois',
    },
  ],
  optimization: [
    {
      id: 'data-driven',
      title: 'Décisions basées sur les données',
      description: 'Utilisez les analytics Bapica pour piloter votre stratégie',
      category: 'optimization',
      status: 'locked',
      impact: 'high',
      estimatedTimeToComplete: '1-2 mois',
    },
    {
      id: 'full-automation',
      title: 'Automatisation quasi-complète',
      description: '80%+ des tâches répétitives sont automatisées',
      category: 'optimization',
      status: 'locked',
      impact: 'transformational',
      estimatedTimeToComplete: '3-6 mois',
    },
    {
      id: 'bapica-ambassador',
      title: 'Devenir ambassadeur Bapica',
      description: 'Partagez votre succès et gagnez des revenus d\'affiliation',
      category: 'optimization',
      status: 'locked',
      impact: 'medium',
      estimatedTimeToComplete: 'Accès au programme affiliation',
    },
  ],
}

/**
 * Génère le parcours de progression personnalisé
 */
export function generateProgressTracker(profile: any): ProgressTracker {
  const milestones: Milestone[] = [
    ...MILESTONE_TEMPLATES.onboarding,
    ...MILESTONE_TEMPLATES.activation,
    ...MILESTONE_TEMPLATES.growth,
    ...MILESTONE_TEMPLATES.optimization,
  ]

  // Débloquer les milestones selon le onboarding
  if (profile.sector) {
    milestones.find(m => m.id === 'complete-profile')!.status = 'completed'
    milestones.find(m => m.id === 'complete-profile')!.completedAt = new Date().toISOString()
    milestones.find(m => m.id === 'activate-first-agent')!.status = 'available'
  }

  if (profile.recommendedAgents?.length > 0) {
    milestones.find(m => m.id === 'activate-first-agent')!.agentInvolved = profile.recommendedAgents[0]
  }

  // Calculer la progression
  const completed = milestones.filter(m => m.status === 'completed').length
  const available = milestones.filter(m => m.status === 'available').length
  const total = milestones.length
  const progress = Math.round((completed / Math.max(completed + available, 1)) * 100)

  const nextMilestone = milestones.find(m => m.status === 'available')

  // Réalisations récentes
  const recentAchievements: string[] = []
  milestones.filter(m => m.status === 'completed').slice(-3).forEach(m => {
    recentAchievements.push(`✅ ${m.title}`)
  })

  // Streak (simulé pour l'instant)
  const streak = profile.streak || 1

  return {
    overallProgress: Math.min(progress, 100),
    stage: completed <= 3 ? 'onboarding' : completed <= 6 ? 'activation' : completed <= 9 ? 'growth' : 'optimization',
    completedMilestones: completed,
    totalMilestones: total,
    nextMilestone,
    recentAchievements,
    streak,
    lastActivity: new Date().toISOString(),
  }
}

/**
 * Calcule le niveau de maturité Bapica (1-5)
 */
export function getMaturityLevel(profile: any): { level: number; label: string; description: string } {
  const score = profile.maturityScore || 0
  if (score >= 90) return { level: 5, label: 'Expert', description: 'Automatisation avancée, décisions data-driven' }
  if (score >= 70) return { level: 4, label: 'Confirmé', description: 'Processus optimisés, ROI positif' }
  if (score >= 50) return { level: 3, label: 'Intermédiaire', description: 'Agents actifs, premiers résultats' }
  if (score >= 30) return { level: 2, label: 'Débutant', description: 'Profil complété, découverte des agents' }
  return { level: 1, label: 'Nouveau', description: 'Premiers pas avec l\'IA' }
}

/**
 * Calcule l'impact cumulé estimé
 */
export function getCumulativeImpact(profile: any): {
  hoursSavedPerMonth: number
  revenuePotential: string
  growthAcceleration: string
} {
  const agentCount = profile.recommendedAgents?.length || 0
  const hoursPerAgent = 8  // moyenne d'heures économisées par agent par semaine
  const hoursPerMonth = agentCount * hoursPerAgent * 4
  
  // Revenue potential based on sector
  const sectorMultiplier = profile.sector === 'saas' ? 2.5 
    : profile.sector === 'ecommerce' ? 2.0 
    : profile.sector === 'services' ? 1.8 
    : 1.5

  const baseRevenue = profile.monthlyRevenue ? parseInt(profile.monthlyRevenue) || 5000 : 5000
  const revenuePotential = Math.round(baseRevenue * sectorMultiplier)

  return {
    hoursSavedPerMonth: hoursPerMonth,
    revenuePotential: `${revenuePotential}€/mois`,
    growthAcceleration: profile.digitalMaturity === 'high' ? '2-3x plus rapide' 
      : profile.digitalMaturity === 'medium' ? '1.5-2x plus rapide' 
      : 'Potentiel x2 avec automatisation',
  }
}
