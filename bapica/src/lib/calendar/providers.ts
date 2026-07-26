// Écriture directe dans l'agenda du client — Google Calendar & Outlook (Microsoft Graph),
// via OAuth 2.0. Parité Limova : Tom/Elio/Charly « créent l'événement dans Google Calendar
// ou Outlook ». Ici, à la validation d'une action 'calendar', si le client a connecté son
// agenda on écrit directement dedans ; sinon on retombe sur le .ics (calendar-tools.ts).
//
// ÉCRIT « à l'aveugle » (non testable en sandbox : pas de clés + réseau bloqué). Prérequis
// prod : app Google (scope calendar.events) et/ou app Microsoft (scope Calendars.ReadWrite),
// + variables GOOGLE_CLIENT_ID/SECRET et MICROSOFT_CLIENT_ID/SECRET (voir env.ts).

import { getConnection, saveConnection } from '@/lib/social/store'
import type { RdvInput } from '@/lib/tools/calendar-tools'

export type CalendarPlatform = 'google_calendar' | 'outlook_calendar'

const GOOGLE_SCOPE = 'https://www.googleapis.com/auth/calendar.events'
const OUTLOOK_SCOPE = 'offline_access Calendars.ReadWrite'
const GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
const OUTLOOK_TOKEN_URL = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'
const EMAIL_RE = /.+@.+\..+/

function appBase(): string {
  return (process.env.NEXT_PUBLIC_APP_URL || '').replace(/\/$/, '')
}

/** Fuseau par défaut des rendez-vous (marché FR par défaut, surchargeable). */
function timeZone(): string {
  return process.env.DEFAULT_TIMEZONE || 'Europe/Paris'
}

export function googleConfigured(): boolean {
  return !!(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET)
}
export function outlookConfigured(): boolean {
  return !!(process.env.MICROSOFT_CLIENT_ID && process.env.MICROSOFT_CLIENT_SECRET)
}

export function googleRedirectUri(): string {
  return process.env.GOOGLE_REDIRECT_URI || `${appBase()}/api/calendar/google/callback`
}
export function outlookRedirectUri(): string {
  return process.env.MICROSOFT_REDIRECT_URI || `${appBase()}/api/calendar/outlook/callback`
}

export function googleAuthUrl(state: string): string {
  const p = new URLSearchParams({
    client_id: process.env.GOOGLE_CLIENT_ID || '',
    redirect_uri: googleRedirectUri(),
    response_type: 'code',
    scope: GOOGLE_SCOPE,
    access_type: 'offline',
    prompt: 'consent',
    include_granted_scopes: 'true',
    state,
  })
  return `https://accounts.google.com/o/oauth2/v2/auth?${p.toString()}`
}

export function outlookAuthUrl(state: string): string {
  const p = new URLSearchParams({
    client_id: process.env.MICROSOFT_CLIENT_ID || '',
    redirect_uri: outlookRedirectUri(),
    response_type: 'code',
    response_mode: 'query',
    scope: OUTLOOK_SCOPE,
    state,
  })
  return `https://login.microsoftonline.com/common/oauth2/v2.0/authorize?${p.toString()}`
}

interface TokenSet { accessToken: string; refreshToken?: string | null; expiresIn: number }

async function postForm(url: string, form: Record<string, string>): Promise<any> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams(form).toString(),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok || !data.access_token) {
    throw new Error(data.error_description || data.error || `HTTP ${res.status}`)
  }
  return data
}

export async function exchangeGoogleCode(code: string): Promise<TokenSet> {
  const d = await postForm(GOOGLE_TOKEN_URL, {
    code,
    client_id: process.env.GOOGLE_CLIENT_ID || '',
    client_secret: process.env.GOOGLE_CLIENT_SECRET || '',
    redirect_uri: googleRedirectUri(),
    grant_type: 'authorization_code',
  })
  return { accessToken: d.access_token, refreshToken: d.refresh_token || null, expiresIn: Number(d.expires_in) || 0 }
}

export async function exchangeOutlookCode(code: string): Promise<TokenSet> {
  const d = await postForm(OUTLOOK_TOKEN_URL, {
    code,
    client_id: process.env.MICROSOFT_CLIENT_ID || '',
    client_secret: process.env.MICROSOFT_CLIENT_SECRET || '',
    redirect_uri: outlookRedirectUri(),
    grant_type: 'authorization_code',
    scope: OUTLOOK_SCOPE,
  })
  return { accessToken: d.access_token, refreshToken: d.refresh_token || null, expiresIn: Number(d.expires_in) || 0 }
}

async function refreshGoogle(refreshToken: string): Promise<TokenSet> {
  const d = await postForm(GOOGLE_TOKEN_URL, {
    refresh_token: refreshToken,
    client_id: process.env.GOOGLE_CLIENT_ID || '',
    client_secret: process.env.GOOGLE_CLIENT_SECRET || '',
    grant_type: 'refresh_token',
  })
  return { accessToken: d.access_token, refreshToken: d.refresh_token || null, expiresIn: Number(d.expires_in) || 0 }
}

async function refreshOutlook(refreshToken: string): Promise<TokenSet> {
  const d = await postForm(OUTLOOK_TOKEN_URL, {
    refresh_token: refreshToken,
    client_id: process.env.MICROSOFT_CLIENT_ID || '',
    client_secret: process.env.MICROSOFT_CLIENT_SECRET || '',
    grant_type: 'refresh_token',
    scope: OUTLOOK_SCOPE,
  })
  return { accessToken: d.access_token, refreshToken: d.refresh_token || null, expiresIn: Number(d.expires_in) || 0 }
}

/**
 * Renvoie un access_token valide pour la connexion demandée, en le rafraîchissant
 * (et en le persistant) s'il est expiré ou proche de l'expiration.
 */
async function freshAccessToken(userId: string, platform: CalendarPlatform): Promise<{ token: string } | { error: string }> {
  const conn = await getConnection(userId, platform).catch(() => null)
  if (!conn) return { error: 'not-connected' }
  const c = conn as { access_token?: string; refresh_token?: string; expires_at?: string; external_id?: string | null }
  let access = c.access_token || ''
  const refresh = c.refresh_token || ''
  const expiresAt = c.expires_at ? Date.parse(c.expires_at) : 0
  const nearExpiry = expiresAt > 0 && expiresAt - Date.now() < 60_000

  if ((nearExpiry || !access) && refresh) {
    try {
      const t = platform === 'google_calendar' ? await refreshGoogle(refresh) : await refreshOutlook(refresh)
      access = t.accessToken
      await saveConnection(userId, platform, {
        accessToken: t.accessToken,
        refreshToken: t.refreshToken || refresh, // Google ne renvoie pas toujours un nouveau refresh
        expiresAt: t.expiresIn ? new Date(Date.now() + t.expiresIn * 1000).toISOString() : null,
        externalId: c.external_id ?? null,
      })
    } catch (e) {
      if (!access) return { error: `Rafraîchissement du jeton : ${e instanceof Error ? e.message : String(e)}` }
      // sinon on tente quand même avec l'ancien token
    }
  }
  if (!access) return { error: 'no-token' }
  return { token: access }
}

/** Calcule les dateTime locaux (heure murale) de début et de fin. */
function localTimes(rdv: RdvInput): { start: string; end: string } | null {
  const dm = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(rdv.date || ''))
  const tm = /^(\d{1,2}):(\d{2})$/.exec(String(rdv.time || ''))
  if (!dm || !tm) return null
  const y = Number(dm[1]); const mo = Number(dm[2]); const d = Number(dm[3])
  const h = Number(tm[1]); const mi = Number(tm[2])
  const dur = Math.min(Math.max(Number(rdv.duration_minutes) || 30, 5), 8 * 60)
  const startMs = Date.UTC(y, mo - 1, d, h, mi, 0)
  if (Number.isNaN(startMs)) return null
  const pad = (n: number) => String(n).padStart(2, '0')
  const fmt = (dt: Date) =>
    `${dt.getUTCFullYear()}-${pad(dt.getUTCMonth() + 1)}-${pad(dt.getUTCDate())}` +
    `T${pad(dt.getUTCHours())}:${pad(dt.getUTCMinutes())}:00`
  return { start: fmt(new Date(startMs)), end: fmt(new Date(startMs + dur * 60_000)) }
}

async function createGoogleEvent(token: string, rdv: RdvInput, t: { start: string; end: string }): Promise<{ ok: boolean; link?: string; error?: string }> {
  const body: Record<string, unknown> = {
    summary: rdv.title || 'Rendez-vous',
    start: { dateTime: t.start, timeZone: timeZone() },
    end: { dateTime: t.end, timeZone: timeZone() },
  }
  if (rdv.location) body.location = rdv.location
  if (rdv.description) body.description = rdv.description
  const hasGuest = !!(rdv.attendee && EMAIL_RE.test(rdv.attendee))
  if (hasGuest) body.attendees = [{ email: rdv.attendee }]

  // sendUpdates=all → Google ENVOIE l'invitation par email à l'invité (sinon, par défaut,
  // le participant est ajouté mais ne reçoit rien). C'est ce qui fait que le client « voit » le RDV.
  const url = `https://www.googleapis.com/calendar/v3/calendars/primary/events${hasGuest ? '?sendUpdates=all' : ''}`
  const res = await fetch(url, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(15000),
  })
  const d = await res.json().catch(() => ({}))
  if (!res.ok) return { ok: false, error: `Google Calendar : ${d?.error?.message || `HTTP ${res.status}`}` }
  return { ok: true, link: d.htmlLink }
}

async function createOutlookEvent(token: string, rdv: RdvInput, t: { start: string; end: string }): Promise<{ ok: boolean; link?: string; error?: string }> {
  const body: Record<string, unknown> = {
    subject: rdv.title || 'Rendez-vous',
    start: { dateTime: t.start, timeZone: timeZone() },
    end: { dateTime: t.end, timeZone: timeZone() },
  }
  if (rdv.description) body.body = { contentType: 'Text', content: rdv.description }
  if (rdv.location) body.location = { displayName: rdv.location }
  if (rdv.attendee && EMAIL_RE.test(rdv.attendee)) {
    body.attendees = [{ emailAddress: { address: rdv.attendee }, type: 'required' }]
  }

  const res = await fetch('https://graph.microsoft.com/v1.0/me/events', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(15000),
  })
  const d = await res.json().catch(() => ({}))
  if (!res.ok) return { ok: false, error: `Outlook : ${d?.error?.message || `HTTP ${res.status}`}` }
  return { ok: true, link: d.webLink }
}

/**
 * Tente d'écrire le RDV dans l'agenda connecté du client (Google d'abord, puis Outlook).
 * - booked=true : événement créé directement (link = URL de l'événement).
 * - booked=false sans error : aucun agenda connecté → le caller retombe sur le .ics.
 * - booked=false avec error : agenda connecté mais l'écriture a échoué → repli .ics + note.
 */
export async function bookOnConnectedCalendar(
  userId: string,
  rdv: RdvInput
): Promise<{ booked: boolean; provider?: string; link?: string; error?: string }> {
  const t = localTimes(rdv)
  if (!t) return { booked: false, error: 'Date/heure invalide.' }

  const google = await getConnection(userId, 'google_calendar').catch(() => null)
  if (google) {
    const ft = await freshAccessToken(userId, 'google_calendar')
    if ('token' in ft) {
      const r = await createGoogleEvent(ft.token, rdv, t)
      if (r.ok) return { booked: true, provider: 'Google Calendar', link: r.link }
      return { booked: false, provider: 'Google Calendar', error: r.error }
    }
    return { booked: false, provider: 'Google Calendar', error: ft.error }
  }

  const outlook = await getConnection(userId, 'outlook_calendar').catch(() => null)
  if (outlook) {
    const ft = await freshAccessToken(userId, 'outlook_calendar')
    if ('token' in ft) {
      const r = await createOutlookEvent(ft.token, rdv, t)
      if (r.ok) return { booked: true, provider: 'Outlook', link: r.link }
      return { booked: false, provider: 'Outlook', error: r.error }
    }
    return { booked: false, provider: 'Outlook', error: ft.error }
  }

  return { booked: false } // aucun agenda connecté → .ics
}
