/**
 * Préréglages IMAP/SMTP des fournisseurs courants — module SANS dépendance serveur,
 * importable côté client (le module email.ts, lui, tire nodemailer/imapflow).
 */
export interface EmailPreset {
  label: string
  imapHost: string
  imapPort: number
  smtpHost: string
  smtpPort: number
  note?: string
}

export const EMAIL_PRESETS: Record<string, EmailPreset> = {
  gmail: { label: 'Gmail', imapHost: 'imap.gmail.com', imapPort: 993, smtpHost: 'smtp.gmail.com', smtpPort: 465, note: 'Utilisez un « mot de passe d’application » Google (pas votre mot de passe habituel).' },
  outlook: { label: 'Outlook / Microsoft 365', imapHost: 'outlook.office365.com', imapPort: 993, smtpHost: 'smtp.office365.com', smtpPort: 587 },
  ovh: { label: 'OVH', imapHost: 'ssl0.ovh.net', imapPort: 993, smtpHost: 'ssl0.ovh.net', smtpPort: 465 },
  gandi: { label: 'Gandi', imapHost: 'mail.gandi.net', imapPort: 993, smtpHost: 'mail.gandi.net', smtpPort: 465 },
  ionos: { label: 'IONOS', imapHost: 'imap.ionos.fr', imapPort: 993, smtpHost: 'smtp.ionos.fr', smtpPort: 465 },
  other: { label: 'Autre (IMAP/SMTP)', imapHost: '', imapPort: 993, smtpHost: '', smtpPort: 465 },
}
