import nodemailer from 'nodemailer'
import { ImapFlow } from 'imapflow'

export { EMAIL_PRESETS, type EmailPreset } from './email-presets'

/**
 * Connexion email par IMAP/SMTP — fonctionne avec N'IMPORTE QUELLE boîte mail
 * (Gmail, Outlook, OVH, Gandi…) sans validation d'éditeur, via un mot de passe
 * d'application. Envoi (SMTP) fiable en serverless ; lecture (IMAP) à la demande.
 */
export interface EmailConfig {
  email: string
  user: string // souvent identique à email
  password: string
  imapHost: string
  imapPort: number
  smtpHost: string
  smtpPort: number
}

function smtpTransport(cfg: EmailConfig) {
  return nodemailer.createTransport({
    host: cfg.smtpHost,
    port: cfg.smtpPort,
    secure: cfg.smtpPort === 465, // 465 = TLS implicite ; 587 = STARTTLS
    auth: { user: cfg.user || cfg.email, pass: cfg.password },
  })
}

/** Vérifie que la connexion fonctionne (SMTP obligatoire, IMAP au mieux). */
export async function verifyEmail(cfg: EmailConfig): Promise<{ ok: boolean; error?: string }> {
  try {
    await smtpTransport(cfg).verify()
  } catch (e) {
    return { ok: false, error: `SMTP : ${String(e instanceof Error ? e.message : e)}` }
  }
  try {
    const client = new ImapFlow({
      host: cfg.imapHost,
      port: cfg.imapPort,
      secure: true,
      auth: { user: cfg.user || cfg.email, pass: cfg.password },
      logger: false,
    })
    await client.connect()
    await client.logout()
  } catch (e) {
    return { ok: false, error: `IMAP : ${String(e instanceof Error ? e.message : e)}` }
  }
  return { ok: true }
}

export async function sendEmail(
  cfg: EmailConfig,
  msg: { to: string; subject: string; text: string }
): Promise<{ ok: boolean; id?: string; error?: string }> {
  try {
    const info = await smtpTransport(cfg).sendMail({
      from: cfg.email,
      to: msg.to,
      subject: msg.subject,
      text: msg.text,
    })
    return { ok: true, id: info.messageId }
  } catch (e) {
    return { ok: false, error: String(e instanceof Error ? e.message : e) }
  }
}

export interface EmailSummary {
  from: string
  subject: string
  date: string
}

/** Lit les N derniers emails de la boîte de réception (en-têtes seulement). */
export async function readRecentEmails(cfg: EmailConfig, limit = 10): Promise<EmailSummary[]> {
  const client = new ImapFlow({
    host: cfg.imapHost,
    port: cfg.imapPort,
    secure: true,
    auth: { user: cfg.user || cfg.email, pass: cfg.password },
    logger: false,
  })
  const out: EmailSummary[] = []
  await client.connect()
  try {
    const lock = await client.getMailboxLock('INBOX')
    try {
      const box = client.mailbox
      const total = box && typeof box !== 'boolean' ? box.exists : 0
      if (total > 0) {
        const start = Math.max(1, total - limit + 1)
        for await (const m of client.fetch(`${start}:*`, { envelope: true })) {
          const env = m.envelope
          out.push({
            from: env?.from?.[0]?.address || env?.from?.[0]?.name || 'Inconnu',
            subject: env?.subject || '(sans objet)',
            date: env?.date ? new Date(env.date).toISOString() : '',
          })
        }
      }
    } finally {
      lock.release()
    }
  } finally {
    await client.logout().catch(() => {})
  }
  return out.reverse() // du plus récent au plus ancien
}
