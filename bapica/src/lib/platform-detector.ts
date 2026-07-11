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
  return [
    {
      name: 'Communication',
      platforms: [
        { id: 'gmail' as IntegrationProvider, name: 'Gmail / Google Workspace', description: 'Envoyez des emails professionnels depuis Bapica' },
        { id: 'slack' as IntegrationProvider, name: 'Slack', description: 'Notifications et messages d\'équipe' },
      ]
    },
    {
      name: 'Comptabilité & Finance',
      platforms: [
        { id: 'pennylane' as IntegrationProvider, name: 'Pennylane', description: 'Facturation, comptabilité, trésorerie' },
        { id: 'stripe' as IntegrationProvider, name: 'Stripe', description: 'Paiements en ligne et abonnements' },
      ]
    },
    {
      name: 'Organisation',
      platforms: [
        { id: 'google_calendar' as IntegrationProvider, name: 'Google Calendar', description: 'Prise de rendez-vous automatique' },
        { id: 'notion' as IntegrationProvider, name: 'Notion', description: 'Documentation et base de connaissances' },
      ]
    },
    {
      name: 'CRM',
      platforms: [
        { id: 'twenty' as IntegrationProvider, name: 'Twenty CRM', description: 'Contacts, pipeline, opportunités' },
      ]
    },
  ]
}
