// Connecteur bancaire — GoCardless Bank Account Data (ex-Nordigen).
// Agrégateur gratuit, 2500+ banques européennes, LECTURE SEULE (soldes + transactions).
// Claire s'en sert pour la surveillance de trésorerie sur des données réelles.
//
// Flux : le client saisit ses secret_id/secret_key (portail GoCardless BAD) → on obtient un
// token → il choisit sa banque → on crée une « requisition » (il s'authentifie chez sa banque
// via un lien) → au retour, on récupère ses comptes → soldes/transactions.
//
// ÉCRIT « à l'aveugle » (non testable en sandbox). Dégrade proprement. Prérequis prod :
// un compte GoCardless Bank Account Data (secret_id + secret_key). Aucune variable Vercel
// requise : les identifiants sont fournis par CHAQUE client (stockés service_role).

import { getConnection, saveConnection } from '@/lib/social/store'

const BASE = 'https://bankaccountdata.gocardless.com/api/v2'
export const BANK_PLATFORM = 'gocardless'

interface BankMeta {
  secretId?: string
  secretKey?: string
  requisitionId?: string
  accountIds?: string[]
}

function readMeta(conn: unknown): BankMeta {
  try { return JSON.parse((conn as { external_id?: string })?.external_id || '{}') } catch { return {} }
}

async function api(token: string, path: string, init?: RequestInit): Promise<{ ok: boolean; status: number; data: any }> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init?.headers || {}),
    },
    signal: AbortSignal.timeout(15000),
  })
  const data = await res.json().catch(() => ({}))
  return { ok: res.ok, status: res.status, data }
}

async function newToken(secretId: string, secretKey: string): Promise<{ access: string; refresh: string; accessExpires: number }> {
  const res = await fetch(`${BASE}/token/new/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ secret_id: secretId, secret_key: secretKey }),
    signal: AbortSignal.timeout(15000),
  })
  const d = await res.json().catch(() => ({}))
  if (!res.ok || !d.access) throw new Error(d.detail || d.summary || `HTTP ${res.status}`)
  return { access: d.access, refresh: d.refresh, accessExpires: Number(d.access_expires) || 86400 }
}

/** Enregistre la connexion à partir des identifiants et obtient un premier token. */
export async function connectBank(userId: string, secretId: string, secretKey: string): Promise<{ ok: boolean; error?: string }> {
  try {
    const t = await newToken(secretId, secretKey)
    await saveConnection(userId, BANK_PLATFORM, {
      accessToken: t.access,
      refreshToken: t.refresh,
      expiresAt: new Date(Date.now() + t.accessExpires * 1000).toISOString(),
      externalId: JSON.stringify({ secretId, secretKey } as BankMeta),
    })
    return { ok: true }
  } catch (e) {
    return { ok: false, error: String(e instanceof Error ? e.message : e) }
  }
}

/** Renvoie un access token valide (rafraîchi via les identifiants stockés si expiré). */
async function freshToken(userId: string): Promise<{ token: string; meta: BankMeta } | { error: string }> {
  const conn = await getConnection(userId, BANK_PLATFORM).catch(() => null)
  if (!conn) return { error: 'not-connected' }
  const meta = readMeta(conn)
  const c = conn as { access_token?: string; expires_at?: string }
  const expiresAt = c.expires_at ? Date.parse(c.expires_at) : 0
  const valid = c.access_token && expiresAt - Date.now() > 60_000
  if (valid) return { token: c.access_token as string, meta }
  if (!meta.secretId || !meta.secretKey) return { error: 'no-credentials' }
  try {
    const t = await newToken(meta.secretId, meta.secretKey)
    await saveConnection(userId, BANK_PLATFORM, {
      accessToken: t.access,
      refreshToken: t.refresh,
      expiresAt: new Date(Date.now() + t.accessExpires * 1000).toISOString(),
      externalId: JSON.stringify(meta),
    })
    return { token: t.access, meta }
  } catch (e) {
    return { error: String(e instanceof Error ? e.message : e) }
  }
}

async function updateMeta(userId: string, patch: Partial<BankMeta>): Promise<void> {
  const conn = await getConnection(userId, BANK_PLATFORM).catch(() => null)
  if (!conn) return
  const meta = { ...readMeta(conn), ...patch }
  const c = conn as { access_token?: string; refresh_token?: string; expires_at?: string }
  await saveConnection(userId, BANK_PLATFORM, {
    accessToken: c.access_token || '',
    refreshToken: c.refresh_token || null,
    expiresAt: c.expires_at || null,
    externalId: JSON.stringify(meta),
  })
}

export async function listInstitutions(userId: string, country: string): Promise<{ ok: boolean; institutions?: { id: string; name: string }[]; error?: string }> {
  const ft = await freshToken(userId)
  if ('error' in ft) return { ok: false, error: ft.error }
  const r = await api(ft.token, `/institutions/?country=${encodeURIComponent((country || 'FR').toUpperCase())}`)
  if (!r.ok) return { ok: false, error: `GoCardless : ${r.data?.detail || `HTTP ${r.status}`}` }
  const institutions = (Array.isArray(r.data) ? r.data : []).map((i: any) => ({ id: String(i.id), name: String(i.name) }))
  return { ok: true, institutions }
}

/** Crée une requisition : renvoie le lien d'authentification à la banque. */
export async function createLink(userId: string, institutionId: string, redirect: string): Promise<{ ok: boolean; link?: string; error?: string }> {
  const ft = await freshToken(userId)
  if ('error' in ft) return { ok: false, error: ft.error }
  const r = await api(ft.token, '/requisitions/', {
    method: 'POST',
    body: JSON.stringify({ institution_id: institutionId, redirect, user_language: 'FR' }),
  })
  if (!r.ok || !r.data?.id) return { ok: false, error: `GoCardless : ${r.data?.detail || JSON.stringify(r.data).slice(0, 200)}` }
  await updateMeta(userId, { requisitionId: String(r.data.id), accountIds: [] })
  return { ok: true, link: r.data.link }
}

/** Après authentification : récupère les comptes liés. */
export async function refreshAccounts(userId: string): Promise<{ ok: boolean; accounts?: string[]; error?: string }> {
  const ft = await freshToken(userId)
  if ('error' in ft) return { ok: false, error: ft.error }
  if (!ft.meta.requisitionId) return { ok: false, error: 'Aucune banque liée : lancez d’abord l’autorisation.' }
  const r = await api(ft.token, `/requisitions/${ft.meta.requisitionId}/`)
  if (!r.ok) return { ok: false, error: `GoCardless : ${r.data?.detail || `HTTP ${r.status}`}` }
  const accounts = (r.data?.accounts || []).map(String)
  await updateMeta(userId, { accountIds: accounts })
  return { ok: true, accounts }
}

export async function bankStatus(userId: string): Promise<{ connected: boolean; linked: boolean; accounts: number }> {
  const conn = await getConnection(userId, BANK_PLATFORM).catch(() => null)
  if (!conn) return { connected: false, linked: false, accounts: 0 }
  const meta = readMeta(conn)
  return { connected: true, linked: !!meta.requisitionId, accounts: (meta.accountIds || []).length }
}

/** Lecture des soldes de tous les comptes liés (pour Claire). */
export async function readBalances(userId: string): Promise<{ ok: boolean; balances?: any[]; error?: string }> {
  const ft = await freshToken(userId)
  if ('error' in ft) return { ok: false, error: ft.error }
  const ids = ft.meta.accountIds || []
  if (ids.length === 0) return { ok: false, error: 'Aucun compte lié.' }
  const out: any[] = []
  for (const id of ids.slice(0, 5)) {
    const r = await api(ft.token, `/accounts/${id}/balances/`)
    if (r.ok) out.push({ account: id, balances: r.data?.balances })
  }
  return { ok: true, balances: out }
}

/** Transactions récentes d'un compte (ou du premier compte lié). */
export async function readTransactions(userId: string, accountId?: string): Promise<{ ok: boolean; transactions?: any; error?: string }> {
  const ft = await freshToken(userId)
  if ('error' in ft) return { ok: false, error: ft.error }
  const id = accountId || (ft.meta.accountIds || [])[0]
  if (!id) return { ok: false, error: 'Aucun compte lié.' }
  const r = await api(ft.token, `/accounts/${id}/transactions/`)
  if (!r.ok) return { ok: false, error: `GoCardless : ${r.data?.detail || `HTTP ${r.status}`}` }
  // On borne : GoCardless renvoie booked + pending, parfois volumineux.
  const booked = (r.data?.transactions?.booked || []).slice(0, 40)
  return { ok: true, transactions: { account: id, booked } }
}
