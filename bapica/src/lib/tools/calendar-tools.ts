// Outil « prendre rendez-vous » — parité Limova (Tom, Elio, Charly prennent RDV dans
// Google Calendar / Outlook). L'agent PROPOSE le RDV ; l'utilisateur valide dans
// « Actions à valider ». À la validation, on produit un fichier .ics standard (RFC 5545)
// que le client importe dans n'importe quel agenda (Google, Outlook, Apple) — donc la
// capacité est réelle de bout en bout, même sans OAuth agenda branché.

export interface RdvInput {
  title?: string
  date?: string // AAAA-MM-JJ
  time?: string // HH:MM (24h)
  duration_minutes?: number
  attendee?: string // email de l'invité (optionnel)
  location?: string
  description?: string
}

/** Échappe les caractères spéciaux d'une valeur iCalendar (RFC 5545 §3.3.11). */
function escapeIcs(value: string): string {
  return String(value)
    .replace(/\\/g, '\\\\')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,')
    .replace(/\r?\n/g, '\\n')
}

function pad(n: number): string {
  return String(n).padStart(2, '0')
}

/** Formate un instant UTC en AAAAMMJJTHHMMSSZ. */
function toUtcStamp(d: Date): string {
  return (
    `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}` +
    `T${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}${pad(d.getUTCSeconds())}Z`
  )
}

/**
 * Construit le contenu .ics d'un événement.
 * L'heure fournie est traitée comme « heure locale flottante » (sans fuseau) : les
 * applications d'agenda l'importent à l'heure murale indiquée, ce qui correspond à
 * l'intention « RDV le 22/07 à 14h00 » sans avoir à connaître le fuseau du client.
 */
export function buildIcs(input: RdvInput): { ok: boolean; ics?: string; start?: string; end?: string; error?: string } {
  const date = String(input.date || '').trim()
  const time = String(input.time || '').trim()
  const dm = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date)
  const tm = /^(\d{1,2}):(\d{2})$/.exec(time)
  if (!dm) return { ok: false, error: 'Date invalide (format attendu AAAA-MM-JJ).' }
  if (!tm) return { ok: false, error: 'Heure invalide (format attendu HH:MM).' }

  const [, y, mo, d] = dm.map(Number) as unknown as [string, number, number, number]
  const [, h, mi] = tm.map(Number) as unknown as [string, number, number]
  const duration = Math.min(Math.max(Number(input.duration_minutes) || 30, 5), 8 * 60)

  // Base UTC pour l'arithmétique (préserve l'heure murale telle que saisie).
  const startMs = Date.UTC(y, mo - 1, d, h, mi, 0)
  if (Number.isNaN(startMs)) return { ok: false, error: 'Date/heure invalide.' }
  const start = new Date(startMs)
  const end = new Date(startMs + duration * 60_000)

  // Heure locale flottante (sans Z) : AAAAMMJJTHHMMSS
  const floating = (dt: Date) =>
    `${dt.getUTCFullYear()}${pad(dt.getUTCMonth() + 1)}${pad(dt.getUTCDate())}` +
    `T${pad(dt.getUTCHours())}${pad(dt.getUTCMinutes())}${pad(dt.getUTCSeconds())}`

  const uid = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}@bapica.com`
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Bapica//RDV//FR',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    'BEGIN:VEVENT',
    `UID:${uid}`,
    `DTSTAMP:${toUtcStamp(new Date())}`,
    `DTSTART:${floating(start)}`,
    `DTEND:${floating(end)}`,
    `SUMMARY:${escapeIcs(input.title || 'Rendez-vous')}`,
  ]
  if (input.location) lines.push(`LOCATION:${escapeIcs(input.location)}`)
  if (input.description) lines.push(`DESCRIPTION:${escapeIcs(input.description)}`)
  if (input.attendee && /.+@.+\..+/.test(input.attendee)) {
    lines.push(`ATTENDEE;RSVP=TRUE;CN=${escapeIcs(input.attendee)}:mailto:${input.attendee}`)
  }
  lines.push('STATUS:CONFIRMED', 'END:VEVENT', 'END:VCALENDAR')

  // RFC 5545 : lignes séparées par CRLF.
  return { ok: true, ics: lines.join('\r\n'), start: start.toISOString(), end: end.toISOString() }
}

/** Résumé lisible présenté à l'utilisateur pour validation. */
export function rdvSummary(input: RdvInput): string {
  const who = input.attendee ? ` avec ${input.attendee}` : ''
  const where = input.location ? ` (${input.location})` : ''
  return `RDV : ${input.title || 'Rendez-vous'}${who} — le ${input.date} à ${input.time}${where}`
}

// ─── Définition d'outil exposée aux agents ──────────────────────────────────

export const proposeRdvTool = {
  name: 'proposer_rdv',
  description:
    "PROPOSE la prise d'un rendez-vous dans l'agenda du client (Google Calendar, Outlook, Apple). " +
    "Tu ne le crées PAS toi-même : il est mis en attente et l'utilisateur le valide d'un clic dans " +
    "« Actions à valider », ce qui génère un événement d'agenda (.ics) prêt à importer. Utilise-le dès " +
    "qu'un créneau est convenu (appel entrant qualifié, prospect qui accepte un RDV, réunion planifiée). " +
    "Donne un titre clair, la date (AAAA-MM-JJ), l'heure (HH:MM) et la durée.",
  input_schema: {
    type: 'object' as const,
    properties: {
      title: { type: 'string', description: "Objet du rendez-vous (ex : « Visite chantier — M. Dupont »)" },
      date: { type: 'string', description: 'Date au format AAAA-MM-JJ' },
      time: { type: 'string', description: 'Heure de début au format HH:MM (24h)' },
      duration_minutes: { type: 'number', description: 'Durée en minutes (défaut 30)' },
      attendee: { type: 'string', description: "Email de l'invité (optionnel)" },
      location: { type: 'string', description: 'Lieu ou lien visio (optionnel)' },
      description: { type: 'string', description: 'Notes / ordre du jour (optionnel)' },
    },
    required: ['title', 'date', 'time'],
  },
}
