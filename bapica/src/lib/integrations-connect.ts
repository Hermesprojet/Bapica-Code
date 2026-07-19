import type { IntegrationProvider } from './integrations'

/**
 * Méthode de connexion par plateforme.
 * - 'api_key' : le client colle une clé/jeton → connexion immédiate (stockée par client).
 * - 'oauth'   : nécessite un flux OAuth déclaré côté Bapica (LinkedIn est branché).
 * - 'soon'    : demande un dossier fournisseur (vérification Google/Microsoft, agrégateur
 *               bancaire DSP2, partenariat éditeur…) → affiché « Bientôt » avec la raison.
 */
export type ConnectMethod = 'api_key' | 'oauth' | 'soon'

// Plateformes réellement connectables tout de suite avec une clé/jeton d'API.
const API_KEY_PROVIDERS = new Set<string>([
  // Finance & paiement
  'stripe', 'pennylane', 'mollie', 'square', 'wise', 'qonto', 'zoho_books',
  // CRM
  'hubspot', 'pipedrive', 'twenty', 'zoho_crm',
  // Email marketing
  'brevo', 'mailchimp', 'mailjet', 'sendgrid', 'resend',
  // E-commerce
  'shopify', 'woocommerce', 'prestashop',
  // Productivité / projet
  'notion', 'slack', 'discord', 'trello', 'asana', 'monday', 'clickup', 'jira',
  // Agenda
  'calendly',
])

// Plateformes avec flux OAuth déjà branché côté Bapica.
const OAUTH_PROVIDERS = new Set<string>(['linkedin'])

// Raison affichée pour les plateformes pas encore ouvertes.
const SOON_REASON: Record<string, string> = {
  gmail: "Nécessite la validation Google (scopes Gmail restreints, audit de sécurité).",
  outlook: 'Nécessite une app Microsoft validée.',
  office365: 'Nécessite une app Microsoft validée.',
  teams: 'Nécessite une app Microsoft validée.',
  google_calendar: 'Nécessite la validation Google.',
  outlook_calendar: 'Nécessite une app Microsoft validée.',
  salesforce: 'OAuth éditeur à déclarer.',
  quickbooks: 'OAuth éditeur à déclarer.',
  xero: 'OAuth éditeur à déclarer.',
  sage: 'Partenariat éditeur requis.',
  cegid: 'Partenariat éditeur requis.',
  revolut: 'Accès bancaire : OAuth + certificat (agrégateur DSP2 recommandé).',
  paypal: 'OAuth éditeur à déclarer.',
  adyen: 'Contrat éditeur requis.',
  facebook: 'App Meta à faire valider.',
  instagram: 'App Meta à faire valider.',
  whatsapp: 'Se configure dans « Canaux » (Embedded Signup).',
  telegram: 'Se configure dans « Canaux » (connexion en 1 clic).',
}

export function connectMethodFor(provider: string): ConnectMethod {
  if (OAUTH_PROVIDERS.has(provider)) return 'oauth'
  if (API_KEY_PROVIDERS.has(provider)) return 'api_key'
  return 'soon'
}

export function soonReasonFor(provider: string): string {
  return SOON_REASON[provider] || 'Intégration en préparation.'
}

/** Aide contextuelle : où trouver la clé, par plateforme. */
export function apiKeyHintFor(provider: string): string {
  const hints: Record<string, string> = {
    stripe: 'Clé secrète Stripe (Développeurs → Clés API), commence par sk_',
    pennylane: 'Pennylane → Paramètres → API → jeton',
    qonto: 'Qonto → Paramètres → Intégrations → clé API (login:secret)',
    hubspot: 'HubSpot → Paramètres → Intégrations → Private App token',
    brevo: 'Brevo → SMTP & API → Créer une clé API v3',
    notion: 'Notion → Paramètres → Intégrations → jeton interne',
    slack: 'Slack API → Your App → Bot User OAuth Token (xoxb-)',
    shopify: 'Admin Shopify → Apps → Développer → jeton Admin API',
    calendly: 'Calendly → Intégrations → jeton d’accès personnel',
    twenty: 'Twenty → Paramètres → API → jeton',
  }
  return hints[provider] || 'Clé ou jeton d’API fourni par la plateforme.'
}

export function isKnownProvider(provider: string, catalogIds: string[]): provider is IntegrationProvider {
  return catalogIds.includes(provider)
}
