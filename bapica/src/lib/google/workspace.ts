// Écriture directe dans Google Docs / Sheets (Drive) via OAuth 2.0.
// Complète « Documents » : un fichier produit par un agent peut être exporté en Google
// Sheet (tableaux) ou Google Doc (textes) dans le Drive du client.
//
// ÉCRIT « à l'aveugle » (non testable en sandbox : pas de clés + réseau bloqué). Prérequis
// prod : app Google (mêmes GOOGLE_CLIENT_ID/SECRET que l'agenda) avec les APIs Drive/Docs/
// Sheets activées et les scopes ci-dessous, + la redirection /api/google/workspace/callback.

import { getConnection, saveConnection } from '@/lib/social/store'

const SCOPE = [
  'https://www.googleapis.com/auth/drive.file',
  'https://www.googleapis.com/auth/documents',
  'https://www.googleapis.com/auth/spreadsheets',
].join(' ')
const TOKEN_URL = 'https://oauth2.googleapis.com/token'
export const WORKSPACE_PLATFORM = 'google_workspace'

function appBase(): string {
  return (process.env.NEXT_PUBLIC_APP_URL || '').replace(/\/$/, '')
}

export function workspaceConfigured(): boolean {
  return !!(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET)
}

export function workspaceRedirectUri(): string {
  return process.env.GOOGLE_WORKSPACE_REDIRECT_URI || `${appBase()}/api/google/workspace/callback`
}

export function workspaceAuthUrl(state: string): string {
  const p = new URLSearchParams({
    client_id: process.env.GOOGLE_CLIENT_ID || '',
    redirect_uri: workspaceRedirectUri(),
    response_type: 'code',
    scope: SCOPE,
    access_type: 'offline',
    prompt: 'consent',
    include_granted_scopes: 'true',
    state,
  })
  return `https://accounts.google.com/o/oauth2/v2/auth?${p.toString()}`
}

interface TokenSet { accessToken: string; refreshToken?: string | null; expiresIn: number }

async function postForm(form: Record<string, string>): Promise<any> {
  const res = await fetch(TOKEN_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams(form).toString(),
  })
  const d = await res.json().catch(() => ({}))
  if (!res.ok || !d.access_token) throw new Error(d.error_description || d.error || `HTTP ${res.status}`)
  return d
}

export async function exchangeWorkspaceCode(code: string): Promise<TokenSet> {
  const d = await postForm({
    code,
    client_id: process.env.GOOGLE_CLIENT_ID || '',
    client_secret: process.env.GOOGLE_CLIENT_SECRET || '',
    redirect_uri: workspaceRedirectUri(),
    grant_type: 'authorization_code',
  })
  return { accessToken: d.access_token, refreshToken: d.refresh_token || null, expiresIn: Number(d.expires_in) || 0 }
}

async function refresh(refreshToken: string): Promise<TokenSet> {
  const d = await postForm({
    refresh_token: refreshToken,
    client_id: process.env.GOOGLE_CLIENT_ID || '',
    client_secret: process.env.GOOGLE_CLIENT_SECRET || '',
    grant_type: 'refresh_token',
  })
  return { accessToken: d.access_token, refreshToken: d.refresh_token || null, expiresIn: Number(d.expires_in) || 0 }
}

async function freshToken(userId: string): Promise<{ token: string } | { error: string }> {
  const conn = await getConnection(userId, WORKSPACE_PLATFORM).catch(() => null)
  if (!conn) return { error: 'not-connected' }
  const c = conn as { access_token?: string; refresh_token?: string; expires_at?: string }
  let access = c.access_token || ''
  const refreshTok = c.refresh_token || ''
  const expiresAt = c.expires_at ? Date.parse(c.expires_at) : 0
  const nearExpiry = expiresAt > 0 && expiresAt - Date.now() < 60_000
  if ((nearExpiry || !access) && refreshTok) {
    try {
      const t = await refresh(refreshTok)
      access = t.accessToken
      await saveConnection(userId, WORKSPACE_PLATFORM, {
        accessToken: t.accessToken,
        refreshToken: t.refreshToken || refreshTok,
        expiresAt: t.expiresIn ? new Date(Date.now() + t.expiresIn * 1000).toISOString() : null,
      })
    } catch (e) {
      if (!access) return { error: `Rafraîchissement du jeton : ${e instanceof Error ? e.message : String(e)}` }
    }
  }
  if (!access) return { error: 'no-token' }
  return { token: access }
}

export function isWorkspaceConnected(userId: string): Promise<boolean> {
  return getConnection(userId, WORKSPACE_PLATFORM).then((c) => !!c).catch(() => false)
}

// ─── Conversions ─────────────────────────────────────────────────────────────

/** Parse un CSV (séparateur virgule, guillemets échappés en «""», BOM toléré). */
export function parseCsv(text: string): string[][] {
  const s = text.replace(/^﻿/, '')
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let inQuotes = false
  for (let i = 0; i < s.length; i++) {
    const c = s[i]
    if (inQuotes) {
      if (c === '"') { if (s[i + 1] === '"') { cell += '"'; i++ } else inQuotes = false }
      else cell += c
    } else if (c === '"') inQuotes = true
    else if (c === ',') { row.push(cell); cell = '' }
    else if (c === '\n') { row.push(cell); rows.push(row); row = []; cell = '' }
    else if (c === '\r') { /* ignore */ }
    else cell += c
  }
  if (cell.length || row.length) { row.push(cell); rows.push(row) }
  return rows
}

/** Retire le balisage HTML/Markdown pour obtenir un texte brut lisible dans un Doc. */
export function toPlainText(input: string): string {
  return input
    .replace(/<\/(p|h[1-6]|tr|li|div)>/gi, '\n')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/^#{1,6}\s+/gm, '').replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\n{3,}/g, '\n\n').trim()
}

// ─── Création ────────────────────────────────────────────────────────────────

export async function createSheet(userId: string, title: string, rows: string[][]): Promise<{ ok: boolean; url?: string; error?: string }> {
  const ft = await freshToken(userId)
  if ('error' in ft) return { ok: false, error: ft.error }
  const cellVal = (v: string) => (/^-?\d+(\.\d+)?$/.test(v.trim()) && v.trim() !== '' ? { userEnteredValue: { numberValue: Number(v) } } : { userEnteredValue: { stringValue: v } })
  const rowData = rows.map((r) => ({ values: r.map(cellVal) }))
  const res = await fetch('https://sheets.googleapis.com/v4/spreadsheets', {
    method: 'POST',
    headers: { Authorization: `Bearer ${ft.token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ properties: { title }, sheets: [{ properties: { title: 'Feuille 1' }, data: [{ startRow: 0, startColumn: 0, rowData }] }] }),
    signal: AbortSignal.timeout(15000),
  })
  const d = await res.json().catch(() => ({}))
  if (!res.ok) return { ok: false, error: `Google Sheets : ${d?.error?.message || `HTTP ${res.status}`}` }
  return { ok: true, url: d.spreadsheetUrl || (d.spreadsheetId ? `https://docs.google.com/spreadsheets/d/${d.spreadsheetId}/edit` : undefined) }
}

export async function createDoc(userId: string, title: string, text: string): Promise<{ ok: boolean; url?: string; error?: string }> {
  const ft = await freshToken(userId)
  if ('error' in ft) return { ok: false, error: ft.error }
  // 1) Créer le doc (titre seulement).
  const createRes = await fetch('https://docs.googleapis.com/v1/documents', {
    method: 'POST',
    headers: { Authorization: `Bearer ${ft.token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
    signal: AbortSignal.timeout(15000),
  })
  const created = await createRes.json().catch(() => ({}))
  if (!createRes.ok || !created.documentId) return { ok: false, error: `Google Docs : ${created?.error?.message || `HTTP ${createRes.status}`}` }
  const docId = created.documentId as string
  // 2) Insérer le texte.
  const body = toPlainText(text)
  if (body) {
    await fetch(`https://docs.googleapis.com/v1/documents/${docId}:batchUpdate`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${ft.token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ requests: [{ insertText: { location: { index: 1 }, text: body } }] }),
      signal: AbortSignal.timeout(15000),
    }).catch(() => {})
  }
  return { ok: true, url: `https://docs.google.com/document/d/${docId}/edit` }
}
