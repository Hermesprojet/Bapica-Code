/**
 * Bapica Platform Detector
 * 
 * Détecte automatiquement les outils utilisés par le client
 * et propose les intégrations pertinentes.
 */

import { getAvailableIntegrations, type IntegrationProvider } from './integrations'

export interface DetectedPlatform {
  provider: IntegrationProvider
  name: string
  confidence: 'high' | 'medium' | 'low'
  detectedBy: 'email' | 'domain' | 'declared' | 'heuristic'
  reason: string
  readyToConnect: boolean
}

/**
 * Détecte les plateformes à partir du profil utilisateur
 */
export function detectPlatformsFromProfile(profile: {
  email?: string
  companyName?: string
  sector?: string
  employeeCount?: number
  hasWebsite?: boolean
}): DetectedPlatform[] {
  const detected: DetectedPlatform[] = []
  const email = profile.email || ''
  const domain = email.split('@')[1] || ''

  // 1. Gmail / Google Workspace
  if (domain === 'gmail.com' || domain === 'googlemail.com') {
    detected.push({
      provider: 'gmail', name: 'Gmail',
      confidence: 'high', detectedBy: 'email',
      reason: 'Adresse Gmail détectée',
      readyToConnect: true,
    })
    detected.push({
      provider: 'google_calendar', name: 'Google Calendar',
      confidence: 'high', detectedBy: 'email',
      reason: 'Compte Google = Calendar inclus',
      readyToConnect: true,
    })
  }

  // 2. Domaine professionnel → Google Workspace ou Office 365
  if (domain && domain !== 'gmail.com' && !domain.includes('yahoo') && !domain.includes('hotmail')) {
    detected.push({
      provider: 'gmail', name: 'Google Workspace ou Email Pro',
      confidence: 'medium', detectedBy: 'domain',
      reason: `Domaine professionnel: ${domain}`,
      readyToConnect: false, // besoin de confirmer si Gmail ou Office365
    })
  }

  // 3. Taille entreprise → plateformes probables
  const employees = profile.employeeCount || 0

  // PME 5-50 → Pennylane, Notion probables
  if (employees >= 3) {
    detected.push({
      provider: 'pennylane', name: 'Pennylane',
      confidence: 'medium', detectedBy: 'heuristic',
      reason: `PME de ${employees} employés — outil compta probable`,
      readyToConnect: false,
    })
    detected.push({
      provider: 'notion', name: 'Notion',
      confidence: 'low', detectedBy: 'heuristic',
      reason: 'Collaboration d\'équipe',
      readyToConnect: false,
    })
  }

  // 4. Slack pour équipes > 5
  if (employees >= 5) {
    detected.push({
      provider: 'slack', name: 'Slack',
      confidence: 'medium', detectedBy: 'heuristic',
      reason: `Équipe de ${employees} — messagerie probable`,
      readyToConnect: false,
    })
  }

  // 5. SaaS & Cloud — détection par secteur et taille
  if (domain && domain !== 'gmail.com') {
    // Stockage cloud
    detected.push({
      provider: 'google_drive', name: 'Google Drive',
      confidence: 'medium', detectedBy: 'domain',
      reason: 'Domaine pro → Google Workspace probable',
      readyToConnect: false,
    })
    detected.push({
      provider: 'dropbox', name: 'Dropbox',
      confidence: 'low', detectedBy: 'heuristic',
      reason: 'Alternative stockage cloud fréquente',
      readyToConnect: false,
    })
  }

  // Secteur tech → GitHub, Figma
  if (profile.sector?.match(/tech|saas|web|digital|informatique|dev/i)) {
    detected.push({
      provider: 'github', name: 'GitHub',
      confidence: 'high', detectedBy: 'heuristic',
      reason: 'Secteur tech — code source probable',
      readyToConnect: false,
    })
    detected.push({
      provider: 'figma', name: 'Figma',
      confidence: 'medium', detectedBy: 'heuristic',
      reason: 'Secteur tech — design probable',
      readyToConnect: false,
    })
  }

  // PME > 10 → CRM, ERP probables
  if (employees >= 10) {
    detected.push({
      provider: 'hubspot', name: 'HubSpot',
      confidence: 'medium', detectedBy: 'heuristic',
      reason: 'PME structurée — CRM probable',
      readyToConnect: false,
    })
    detected.push({
      provider: 'salesforce', name: 'Salesforce',
      confidence: 'low', detectedBy: 'heuristic',
      reason: 'Alternative CRM entreprises',
      readyToConnect: false,
    })
    detected.push({
      provider: 'trello', name: 'Trello',
      confidence: 'low', detectedBy: 'heuristic',
      reason: 'Gestion de projet',
      readyToConnect: false,
    })
    detected.push({
      provider: 'asana', name: 'Asana',
      confidence: 'low', detectedBy: 'heuristic',
      reason: 'Gestion de projet',
      readyToConnect: false,
    })
  }

  // Comptabilité internationale
  detected.push({
    provider: 'quickbooks', name: 'QuickBooks',
    confidence: 'low', detectedBy: 'heuristic',
    reason: 'Alternative compta internationale',
    readyToConnect: false,
  })
  detected.push({
    provider: 'xero', name: 'Xero',
    confidence: 'low', detectedBy: 'heuristic',
    reason: 'Alternative compta cloud',
    readyToConnect: false,
  })

  // Automatisation
  detected.push({
    provider: 'zapier', name: 'Zapier',
    confidence: 'low', detectedBy: 'heuristic',
    reason: 'Automatisation no-code',
    readyToConnect: false,
  })
  detected.push({
    provider: 'make', name: 'Make (Integromat)',
    confidence: 'low', detectedBy: 'heuristic',
    reason: 'Automatisation avancée',
    readyToConnect: false,
  })

  return detected
}

/**
 * Détecte l'écosystème complet de la PME et classe par catégorie
 */
export interface PlatformEcosystem {
  communication: DetectedPlatform[]
  accounting: DetectedPlatform[]
  productivity: DetectedPlatform[]
  crm: DetectedPlatform[]
  unclassified: DetectedPlatform[]
}

export function classifyEcosystem(platforms: DetectedPlatform[]): PlatformEcosystem {
  const ecosystem: PlatformEcosystem = {
    communication: [],
    accounting: [],
    productivity: [],
    crm: [],
    unclassified: [],
  }

  const mapping: Record<string, keyof PlatformEcosystem> = {
    gmail: 'communication',
    slack: 'communication',
    pennylane: 'accounting',
    stripe: 'accounting',
    twenty: 'crm',
    google_calendar: 'productivity',
    notion: 'productivity',
  }

  for (const p of platforms) {
    const cat = mapping[p.provider] || 'unclassified'
    ecosystem[cat].push(p)
  }

  return ecosystem
}

/**
 * Score de complétion de l'écosystème
 */
export function getEcosystemScore(ecosystem: PlatformEcosystem): { score: number; missing: string[] } {
  const missing: string[] = []

  if (ecosystem.communication.length === 0) missing.push('Email / Messagerie')
  if (ecosystem.accounting.length === 0) missing.push('Comptabilité / Facturation')
  if (ecosystem.productivity.length === 0) missing.push('Agenda / Documentation')
  if (ecosystem.crm.length === 0) missing.push('CRM')

  const categories = 4
  const filled = categories - missing.length
  return { score: Math.round((filled / categories) * 100), missing }
}

/**
 * Génère un message personnalisé de suggestion d'intégrations
 */
export function generateIntegrationSuggestions(ecosystem: PlatformEcosystem): string {
  const { score, missing } = getEcosystemScore(ecosystem)
  const suggestions: string[] = []

  if (score >= 100) {
    suggestions.push('🎉 Votre écosystème est complet ! Toutes les intégrations sont connectées.')
  } else {
    suggestions.push(`📊 Score de connexion: ${score}%`)
    suggestions.push(`\n🔌 Plateformes manquantes: ${missing.join(', ')}`)

    if (missing.includes('Email / Messagerie')) {
      suggestions.push('\n💡 Connectez Gmail pour permettre aux agents d\'envoyer des emails.')
    }
    if (missing.includes('Comptabilité / Facturation')) {
      suggestions.push('💡 Connectez Pennylane pour la facturation et le suivi de trésorerie.')
    }
    if (missing.includes('Agenda / Documentation')) {
      suggestions.push('💡 Connectez Google Calendar pour la prise de rendez-vous automatique.')
    }
    if (missing.includes('CRM')) {
      suggestions.push('💡 Connectez votre CRM pour le suivi des contacts.')
    }
  }

  return suggestions.join('\n')
}

/**
 * Liste des plateformes que Bapica peut intégrer, groupées par usage
 */
export function getPlatformCategories() {
  const integrations = getAvailableIntegrations()
  const categories = new Map<string, any[]>()
  
  for (const integration of integrations) {
    if (!categories.has(integration.category)) {
      categories.set(integration.category, [])
    }
    categories.get(integration.category)!.push({
      id: integration.id,
      name: integration.name,
      description: integration.description,
    })
  }

  return Array.from(categories.entries()).map(([name, platforms]) => ({ name, platforms }))
}
