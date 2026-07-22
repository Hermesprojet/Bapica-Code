/**
 * Registre central des variables d'environnement de Bapica.
 *
 * SOURCE DE VÉRITÉ des variables attendues : `.env.example` doit rester aligné sur ce
 * fichier, et la route de diagnostic `/api/health/env` s'en sert pour dire, en prod,
 * ce qui est configuré ou non.
 *
 * Principe de sécurité : ce module ne lit QUE la présence (`Boolean`) des variables.
 * Il ne renvoie, ne logge et n'expose JAMAIS leur valeur — comme `/api/channels/status`.
 *
 * Rien n'est instancié ni ne lève d'erreur à l'import : conforme à la règle « pas
 * d'effet de bord au niveau module » (voir CLAUDE.md §8) — le build Vercel ne casse pas
 * quand une variable manque.
 */

/** Un groupe de variables correspondant à une fonctionnalité. */
export type EnvGroup = {
  /** Identifiant stable (clé de la réponse JSON). */
  id: string
  /** Libellé lisible. */
  label: string
  /** true = indispensable au fonctionnement de base de l'app. */
  required: boolean
  /** Variables nécessaires pour que la fonction soit opérationnelle. */
  vars: string[]
  /** Variables facultatives (améliorent la fonction, non bloquantes). */
  optional?: string[]
}

/**
 * Description déclarative de toutes les variables, regroupées par fonction.
 * Aligné sur CLAUDE.md §11 (« À activer en prod »).
 */
export const ENV_GROUPS: EnvGroup[] = [
  {
    id: 'base',
    label: 'Cœur de l\'app (Supabase + Claude)',
    required: true,
    vars: [
      'NEXT_PUBLIC_SUPABASE_URL',
      'NEXT_PUBLIC_SUPABASE_ANON_KEY',
      'SUPABASE_SERVICE_ROLE_KEY',
      'ANTHROPIC_API_KEY',
      'NEXT_PUBLIC_APP_URL',
    ],
    optional: ['NEXT_PUBLIC_SITE_URL'],
  },
  {
    id: 'payment',
    label: 'Paiement (Stripe)',
    required: false,
    vars: [
      'STRIPE_SECRET_KEY',
      'STRIPE_WEBHOOK_SECRET',
      'NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY',
      'STRIPE_PRICE_ESSENTIAL',
      'STRIPE_PRICE_PRO',
    ],
  },
  {
    id: 'rag',
    label: 'RAG documentaire + embeddings (OpenAI)',
    required: false,
    vars: ['OPENAI_API_KEY'],
  },
  {
    id: 'voice',
    label: 'Appels vocaux (Vapi)',
    required: false,
    vars: ['VAPI_API_KEY', 'VAPI_ASSISTANT_ID', 'VAPI_PHONE_NUMBER_ID'],
    optional: ['VAPI_WEBHOOK_SECRET'],
  },
  {
    id: 'video',
    label: 'Rendu vidéo (Runway / HeyGen / ElevenLabs)',
    required: false,
    vars: [
      'RUNWAY_API_KEY',
      'HEYGEN_API_KEY',
      'HEYGEN_AVATAR_ID',
      'HEYGEN_VOICE_ID',
      'ELEVENLABS_API_KEY',
    ],
    optional: ['ELEVENLABS_VOICE_ID'],
  },
  {
    id: 'prospection',
    label: 'Recherche de leads (Apollo / Hunter)',
    required: false,
    vars: [],
    optional: ['APOLLO_API_KEY', 'HUNTER_API_KEY'],
  },
  {
    id: 'web_research',
    label: 'Recherche internet (SerpAPI / Google Places)',
    required: false,
    vars: [],
    optional: ['SERPAPI_KEY', 'GOOGLE_PLACES_API_KEY'],
  },
  {
    id: 'whatsapp_cloud',
    label: 'WhatsApp Cloud API (Meta)',
    required: false,
    vars: ['WHATSAPP_TOKEN', 'WHATSAPP_PHONE_ID', 'WHATSAPP_VERIFY_TOKEN'],
  },
  {
    id: 'whatsapp_twilio',
    label: 'WhatsApp via Twilio',
    required: false,
    vars: ['TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_WHATSAPP_NUMBER'],
  },
  {
    id: 'sms',
    label: 'SMS (Twilio) — comptes rendus d\'appel',
    required: false,
    vars: ['TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN'],
    optional: ['TWILIO_SMS_NUMBER', 'TWILIO_MESSAGING_SERVICE_SID'],
  },
  {
    id: 'telegram',
    label: 'Telegram (bot mono-numéro de repli)',
    required: false,
    vars: ['TELEGRAM_BOT_TOKEN'],
  },
  {
    id: 'messenger',
    label: 'Messenger (Meta)',
    required: false,
    vars: ['MESSENGER_PAGE_TOKEN', 'MESSENGER_VERIFY_TOKEN'],
  },
  {
    id: 'linkedin',
    label: 'Publication LinkedIn',
    required: false,
    vars: ['LINKEDIN_CLIENT_ID', 'LINKEDIN_CLIENT_SECRET'],
    optional: ['LINKEDIN_REDIRECT_URI'],
  },
  {
    id: 'google_calendar',
    label: 'Agenda Google (prise de RDV directe)',
    required: false,
    vars: ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET'],
    optional: ['GOOGLE_REDIRECT_URI', 'DEFAULT_TIMEZONE'],
  },
  {
    id: 'outlook_calendar',
    label: 'Agenda Outlook (prise de RDV directe)',
    required: false,
    vars: ['MICROSOFT_CLIENT_ID', 'MICROSOFT_CLIENT_SECRET'],
    optional: ['MICROSOFT_REDIRECT_URI'],
  },
  {
    id: 'admin',
    label: 'Administrateurs (page Apprentissage)',
    required: false,
    vars: ['NEXT_PUBLIC_ADMIN_EMAILS'],
  },
  {
    id: 'integrations',
    label: 'Intégrations diverses (Twenty CRM, Resend, n8n)',
    required: false,
    vars: [],
    optional: ['TWENTY_WEBHOOK_SECRET', 'RESEND_API_KEY', 'N8N_URL', 'N8N_API_KEY'],
  },
]

/** true si la variable est renseignée (non vide) dans l'environnement courant. */
export function isSet(name: string): boolean {
  const v = process.env[name]
  return typeof v === 'string' && v.trim().length > 0
}

/** Bilan d'un groupe : est-il prêt, et que manque-t-il ? */
export type GroupReport = {
  id: string
  label: string
  required: boolean
  ready: boolean
  missing: string[]
  optionalMissing: string[]
}

/** Bilan complet de l'environnement (présence uniquement, jamais de valeur). */
export type EnvReport = {
  /** true si toutes les variables des groupes « required » sont présentes. */
  ok: boolean
  /** Variables requises manquantes (bloquent le fonctionnement de base). */
  missingRequired: string[]
  groups: GroupReport[]
}

/** Construit le bilan de présence des variables d'environnement. */
export function checkEnv(): EnvReport {
  const groups: GroupReport[] = ENV_GROUPS.map((g) => {
    const missing = g.vars.filter((v) => !isSet(v))
    const optionalMissing = (g.optional || []).filter((v) => !isSet(v))
    return {
      id: g.id,
      label: g.label,
      required: g.required,
      ready: missing.length === 0,
      missing,
      optionalMissing,
    }
  })

  const missingRequired = groups
    .filter((g) => g.required)
    .flatMap((g) => g.missing)

  return { ok: missingRequired.length === 0, missingRequired, groups }
}

/**
 * Résumé lisible du bilan (pour un log serveur au démarrage ou un diagnostic).
 * N'affiche que des noms de variables, jamais de valeurs.
 */
export function formatEnvStatus(report: EnvReport = checkEnv()): string {
  const lines: string[] = []
  lines.push(report.ok
    ? '[env] Variables de base OK.'
    : `[env] ⚠️ Variables de base MANQUANTES : ${report.missingRequired.join(', ')}`)
  for (const g of report.groups) {
    if (g.ready && g.optionalMissing.length === 0) continue
    const parts: string[] = []
    if (!g.ready) parts.push(`manque ${g.missing.join(', ')}`)
    if (g.optionalMissing.length) parts.push(`optionnel absent ${g.optionalMissing.join(', ')}`)
    lines.push(`[env] ${g.label} : ${parts.join(' ; ')}`)
  }
  return lines.join('\n')
}
