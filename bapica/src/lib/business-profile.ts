/**
 * Moteur de Profil Business Intelligent
 * Analyse chaque PME en profondeur pour personnaliser l'expérience Bapica
 */

export interface BusinessProfile {
  // Identité
  companyName?: string
  sector?: string
  subSector?: string
  
  // Taille & Structure
  companySize?: 'independant' | 'TPE' | 'PME' | 'ETI'
  employeeCount?: number
  foundedYear?: number
  
  // Finances
  monthlyRevenue?: string  // "<10k", "10-50k", "50-200k", "200k+"
  businessModel?: 'b2b' | 'b2c' | 'b2b2c' | 'marketplace'
  
  // Maturité
  stage?: 'ideation' | 'early' | 'growth' | 'scaleup' | 'mature'
  
  // Objectifs
  priorities: string[]       // croissance, rentabilité, automatisation, recrutement...
  shortTermGoal?: string     // objectif à 3 mois
  longTermGoal?: string      // objectif à 12 mois
  
  // Points de douleur
  painPoints: string[]       // ce qui freine la croissance
  timeWasters: string[]      // tâches chronophages
  
  // Outils & Tech
  currentTools: string[]     // CRM, compta, email, etc.
  techMaturity?: 'low' | 'medium' | 'high'
  
  // Clients
  customerAcquisition: string[]  // canaux d'acquisition
  avgTicketSize?: string
  customerRetention?: string     // "faible", "moyenne", "forte"
  
  // Concurrence
  competitiveAdvantage?: string
  mainCompetitors?: string
  
  // Analyse IA
  profileSummary?: string        // résumé généré par IA
  recommendedAgents: string[]   // agents recommandés
  growthOpportunities: string[] // opportunités identifiées
  riskFactors: string[]         // risques identifiés
}

/**
 * Analyse le profil complet d'une entreprise à partir des données onboarding
 */
export function analyzeBusinessProfile(data: any): BusinessProfile {
  const profile: BusinessProfile = {
    companyName: data.companyName || data.company_name,
    sector: data.activity,
    companySize: data.companySize || 'TPE',
    employeeCount: data.employeeCount || 1,
    priorities: data.objectives || [],
    painPoints: data.adminTasks || [],
    currentTools: (data.apps || []).map((a: any) => a.name || a),
    customerAcquisition: data.contactMethods || [],
    recommendedAgents: [],
    growthOpportunities: [],
    riskFactors: [],
  }

  // Déduire le business model du secteur
  if (['ecommerce', 'commerce'].includes(profile.sector || '')) {
    profile.businessModel = 'b2c'
  } else if (['services', 'finance', 'saas'].includes(profile.sector || '')) {
    profile.businessModel = 'b2b'
  }

  // Déduire le stade de maturité
  if (profile.employeeCount && profile.employeeCount <= 1) {
    profile.stage = 'early'
  } else if (profile.employeeCount && profile.employeeCount <= 10) {
    profile.stage = 'growth'
  } else if (profile.employeeCount && profile.employeeCount <= 50) {
    profile.stage = 'scaleup'
  }

  // Déduire la maturité tech des outils utilisés
  const advancedTools = ['hubspot', 'salesforce', 'stripe', 'shopify', 'n8n', 'zapier', 'make']
  const hasAdvanced = advancedTools.some(t => 
    profile.currentTools.some(ct => ct.toLowerCase().includes(t))
  )
  profile.techMaturity = hasAdvanced ? 'high' : profile.currentTools.length > 3 ? 'medium' : 'low'

  // Analyser les opportunités de croissance
  if (profile.sector === 'ecommerce') {
    profile.growthOpportunities.push('Automatiser le support client (chatbot + email)')
    profile.growthOpportunities.push('SEO produit : fiches optimisées à grande échelle')
  }
  if (profile.sector === 'services') {
    profile.growthOpportunities.push('Prospection LinkedIn automatisée')
    profile.growthOpportunities.push('Relance automatique des devis en attente')
  }
  if (['immobilier', 'btp'].includes(profile.sector || '')) {
    profile.growthOpportunities.push('Agent téléphonique pour ne rater aucun appel')
    profile.growthOpportunities.push('Suivi automatique des prospects visiteurs')
  }
  if (profile.customerAcquisition.includes('phone')) {
    profile.growthOpportunities.push('Standard IA 24/7 avec prise de messages qualifiée')
  }
  if (['comptabilite', 'factures', 'tva', 'relances'].some(t => 
    profile.painPoints.some(p => p?.toLowerCase().includes(t))
  )) {
    profile.growthOpportunities.push('Facturation et relances 100% automatisées')
  }

  // Identifier les risques
  if (profile.techMaturity === 'low') {
    profile.riskFactors.push('Faible maturité technologique — risque de perte de compétitivité')
  }
  if (profile.employeeCount && profile.employeeCount <= 2) {
    profile.riskFactors.push('Dépendance au fondateur — risque de saturation')
  }
  if (!profile.customerAcquisition || profile.customerAcquisition.length <= 1) {
    profile.riskFactors.push('Dépendance à un seul canal d\'acquisition client')
  }
  if (profile.companySize === 'TPE' && !profile.painPoints.includes('comptable') && !profile.painPoints.includes('factures')) {
    profile.riskFactors.push('Gestion administrative non optimisée')
  }

  // Recommander les agents pertinents
  const agentMap: Record<string, string[]> = {
    ecommerce: ['content', 'support', 'telephone'],
    restauration: ['telephone', 'content', 'general'],
    immobilier: ['prospector', 'closer', 'telephone', 'content'],
    services: ['legal', 'accounting', 'prospector', 'content'],
    sante: ['telephone', 'support', 'legal'],
    formation: ['content', 'video', 'support'],
    btp: ['telephone', 'accounting', 'legal'],
    saas: ['analytics', 'content', 'support', 'scaling'],
    commerce: ['content', 'telephone', 'support'],
    freelance: ['accounting', 'content', 'prospector'],
    logistique: ['telephone', 'analytics', 'accounting'],
    finance: ['prospector', 'closer', 'legal', 'analytics'],
  }
  
  profile.recommendedAgents = agentMap[profile.sector || ''] || ['general', 'content', 'support']

  // Ajouter scaling si l'entreprise est en croissance
  if (profile.stage === 'scaleup' || profile.stage === 'growth') {
    profile.recommendedAgents.push('scaling')
  }

  // Résumé exécutif
  profile.profileSummary = generateSummary(profile)

  return profile
}

function generateSummary(p: BusinessProfile): string {
  const parts = [
    `${p.companyName || 'Entreprise'} — secteur ${p.sector || 'non spécifié'},`,
    `${p.companySize || 'TPE'}, stade ${p.stage || 'croissance'}.`,
    `Priorités : ${p.priorities.join(', ') || 'non définies'}.`,
    `${p.growthOpportunities.length} opportunités, ${p.riskFactors.length} risques.`,
    `Maturité tech : ${p.techMaturity || 'moyenne'}.`,
  ]
  return parts.join(' ')
}
