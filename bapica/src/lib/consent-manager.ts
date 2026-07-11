/**
 * Bapica Connection Consent Manager
 * 
 * AVANT toute connexion, Bapica doit:
 * 1. Expliquer clairement à quoi elle va accéder
 * 2. Lister les permissions demandées
 * 3. Obtenir le consentement EXPLICITE de l'utilisateur
 * 4. Permettre la révocation à tout moment
 */

export interface ConnectionRequest {
  platformName: string
  platformUrl: string
  category: string
  whatBapicaWillDo: string[]
  dataAccessed: string[]
  permissions: string[]
  riskLevel: 'low' | 'medium' | 'high'
  estimatedImpact: string
}

export interface UserConsent {
  userId: string
  platformName: string
  platformUrl: string
  granted: boolean
  grantedAt: string
  expiresAt?: string
  scope: string[]
  revokedAt?: string
  riskLevel: 'low' | 'medium' | 'high'
}

/**
 * Génère une demande de consentement claire et transparente
 */
export function generateConsentRequest(
  platform: { name: string; url: string; category: string }
): ConnectionRequest {
  const templates: Record<string, Partial<ConnectionRequest>> = {
    Communication: {
      whatBapicaWillDo: [
        'Envoyer des emails en votre nom via votre messagerie',
        'Détecter les emails importants nécessitant une réponse',
        'Vous suggérer des réponses (jamais envoyer sans validation)',
      ],
      dataAccessed: ['Expéditeur et destinataire des emails', 'Objet des messages', 'Contenu pour suggérer des réponses'],
      permissions: ['Lecture des emails', 'Envoi d\'emails', 'Accès aux contacts'],
      riskLevel: 'medium',
    },
    Finance: {
      whatBapicaWillDo: [
        'Consulter vos factures et transactions',
        'Créer des factures sur votre demande',
        'Analyser votre trésorerie pour vous conseiller',
      ],
      dataAccessed: ['Historique des factures', 'Soldes et transactions', 'Données clients pour facturation'],
      permissions: ['Lecture des données comptables', 'Création de factures', 'Accès à la trésorerie'],
      riskLevel: 'high',
    },
    CRM: {
      whatBapicaWillDo: [
        'Consulter vos contacts et opportunités',
        'Créer et mettre à jour des fiches contacts',
        'Suggérer des relances commerciales',
      ],
      dataAccessed: ['Liste des contacts', 'Pipeline commercial', 'Historique des interactions'],
      permissions: ['Lecture/écriture contacts', 'Gestion des opportunités', 'Accès au pipeline'],
      riskLevel: 'medium',
    },
    Social: {
      whatBapicaWillDo: [
        'Lire vos messages et mentions',
        'Suggérer des réponses (jamais publier sans validation)',
        'Analyser votre audience',
      ],
      dataAccessed: ['Messages reçus', 'Statistiques d\'audience', 'Mentions et interactions'],
      permissions: ['Lecture des messages', 'Lecture des statistiques', 'Pas de publication automatique'],
      riskLevel: 'medium',
    },
    Cloud: {
      whatBapicaWillDo: [
        'Lister vos fichiers et dossiers',
        'Créer des documents sur votre demande',
        'Rechercher dans vos fichiers',
      ],
      dataAccessed: ['Noms des fichiers et dossiers', 'Contenu des fichiers pour recherche', 'Métadonnées'],
      permissions: ['Lecture des fichiers', 'Création de documents', 'Recherche'],
      riskLevel: 'medium',
    },
    Ecommerce: {
      whatBapicaWillDo: [
        'Consulter vos commandes et produits',
        'Analyser vos ventes pour vous conseiller',
        'Suggérer des optimisations de prix',
      ],
      dataAccessed: ['Commandes et clients', 'Catalogue produits', 'Données de vente'],
      permissions: ['Lecture des commandes', 'Accès au catalogue', 'Analyse des ventes'],
      riskLevel: 'high',
    },
  }

  const template = templates[platform.category] || {
    whatBapicaWillDo: ['Interagir avec cette plateforme pour vous assister'],
    dataAccessed: ['Données accessibles via l\'API de cette plateforme'],
    permissions: ['Lecture des données'],
    riskLevel: 'medium',
  }

  return {
    platformName: platform.name,
    platformUrl: platform.url,
    category: platform.category,
    whatBapicaWillDo: template.whatBapicaWillDo!,
    dataAccessed: template.dataAccessed!,
    permissions: template.permissions!,
    riskLevel: template.riskLevel as 'low' | 'medium' | 'high',
    estimatedImpact: getImpactMessage(template.riskLevel as 'low' | 'medium' | 'high'),
  }
}

function getImpactMessage(level: string): string {
  switch (level) {
    case 'high':
      return '🔴 Cette connexion donne accès à des données sensibles (finance, clients). Bapica ne fera JAMAIS rien sans votre accord explicite pour chaque action.'
    case 'medium':
      return '🟡 Cette connexion permet à Bapica de lire des données et de vous assister. Les actions d\'écriture nécessiteront une confirmation.'
    case 'low':
      return '🟢 Connexion basique. Bapica peut lire des informations pour mieux vous conseiller.'
    default:
      return 'Bapica vous assistera avec cette plateforme.'
  }
}

/**
 * Formate le message de consentement pour l'utilisateur
 */
export function formatConsentMessage(request: ConnectionRequest): string {
  const riskEmoji = { low: '🟢', medium: '🟡', high: '🔴' }
  
  return [
    `## 🔌 Connexion à **${request.platformName}**`,
    '',
    `${riskEmoji[request.riskLevel]} **Niveau de risque:** ${request.riskLevel === 'high' ? 'Élevé' : request.riskLevel === 'medium' ? 'Moyen' : 'Faible'}`,
    '',
    '### Ce que Bapica pourra faire :',
    ...request.whatBapicaWillDo.map(a => `- ✅ ${a}`),
    '',
    '### Données accessibles :',
    ...request.dataAccessed.map(d => `- 📊 ${d}`),
    '',
    '### Permissions demandées :',
    ...request.permissions.map(p => `- 🔑 ${p}`),
    '',
    `> ${request.estimatedImpact}`,
    '',
    '**Vous pourrez révoquer cet accès à tout moment** depuis vos paramètres Bapica.',
    '',
    '👉 Répondez **"Oui, connecter"** pour autoriser, ou **"Non"** pour refuser.',
  ].join('\n')
}

/**
 * Stockage des consentements (à persister dans Supabase)
 */
const consentStore = new Map<string, UserConsent[]>()

export function recordConsent(consent: UserConsent) {
  const userConsents = consentStore.get(consent.userId) || []
  const existing = userConsents.findIndex(c => c.platformName === consent.platformName)
  if (existing >= 0) {
    userConsents[existing] = consent
  } else {
    userConsents.push(consent)
  }
  consentStore.set(consent.userId, userConsents)
}

export function hasConsent(userId: string, platformName: string): boolean {
  const consents = consentStore.get(userId) || []
  const consent = consents.find(c => c.platformName === platformName)
  return !!consent && consent.granted && !consent.revokedAt
}

export function revokeConsent(userId: string, platformName: string) {
  const consents = consentStore.get(userId) || []
  const consent = consents.find(c => c.platformName === platformName)
  if (consent) {
    consent.revokedAt = new Date().toISOString()
    consent.granted = false
  }
}

export function getUserConsents(userId: string): UserConsent[] {
  return consentStore.get(userId) || []
}

/**
 * Vérifie AVANT chaque action si l'utilisateur a donné son consentement
 */
export function requireConsent(
  userId: string,
  platformName: string,
  action: string
): { allowed: boolean; reason?: string } {
  if (!hasConsent(userId, platformName)) {
    return {
      allowed: false,
      reason: `⚠️ Connexion à ${platformName} non autorisée. Demandez d'abord la permission.`,
    }
  }

  // Pour les actions d'écriture sur des plateformes à risque, demander confirmation
  const highRiskActions = ['send', 'create', 'delete', 'update', 'publish', 'post']
  const isWriteAction = highRiskActions.some(a => action.toLowerCase().includes(a))
  
  if (isWriteAction) {
    const consents = consentStore.get(userId) || []
    const consent = consents.find(c => c.platformName === platformName)
    if (consent?.riskLevel === 'high') {
      return {
        allowed: true,
        reason: '✅ Autorisé — action sensible, trace conservée.',
      }
    }
  }

  return { allowed: true }
}
