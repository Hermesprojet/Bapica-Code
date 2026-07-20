import { getConnection } from '@/lib/social/store'
import { readRecentEmails, type EmailConfig, type EmailSummary } from '@/lib/email'

/** Charge la configuration email d'un client depuis social_connections. */
export async function getUserEmailConfig(userId: string): Promise<EmailConfig | null> {
  const conn = await getConnection(userId, 'email').catch(() => null)
  if (!conn) return null
  const password = (conn as { access_token?: string }).access_token || ''
  let meta: Partial<EmailConfig> = {}
  try { meta = JSON.parse((conn as { external_id?: string }).external_id || '{}') } catch { /* ignore */ }
  if (!password || !meta.email || !meta.imapHost || !meta.smtpHost) return null
  return {
    email: meta.email,
    user: meta.user || meta.email,
    password,
    imapHost: meta.imapHost,
    imapPort: meta.imapPort || 993,
    smtpHost: meta.smtpHost,
    smtpPort: meta.smtpPort || 465,
  }
}

export async function runReadEmails(userId: string, limit = 10): Promise<{ ok: boolean; emails?: EmailSummary[]; error?: string }> {
  const cfg = await getUserEmailConfig(userId)
  if (!cfg) return { ok: false, error: "Aucune boîte email connectée (Connexions → Email)." }
  try {
    const emails = await readRecentEmails(cfg, Math.min(Math.max(limit, 1), 20))
    return { ok: true, emails }
  } catch (e) {
    return { ok: false, error: String(e instanceof Error ? e.message : e) }
  }
}

// ─── Définitions d'outils exposées aux agents ───────────────────────────────

export const readEmailsTool = {
  name: 'lire_emails',
  description:
    "Lit les derniers emails reçus dans la boîte email connectée du client (en-têtes : expéditeur, " +
    "objet, date). Utilise-le pour trier, prioriser ou préparer des réponses. Lecture seule.",
  input_schema: {
    type: 'object' as const,
    properties: {
      limit: { type: 'number', description: "Nombre d'emails à lire (max 20, défaut 10)" },
    },
    required: [] as string[],
  },
}

export const proposeEmailTool = {
  name: 'proposer_email',
  description:
    "PROPOSE l'envoi d'un email depuis la boîte du client (réponse à un client, relance de facture, " +
    "message de prospection…). Tu ne l'envoies PAS : il est mis en attente et le client valide d'un clic " +
    "dans « Actions à valider ». Rédige un objet et un corps complets et professionnels.",
  input_schema: {
    type: 'object' as const,
    properties: {
      to: { type: 'string', description: 'Adresse email du destinataire' },
      subject: { type: 'string', description: "Objet de l'email" },
      text: { type: 'string', description: "Corps de l'email (texte)" },
    },
    required: ['to', 'subject', 'text'],
  },
}
