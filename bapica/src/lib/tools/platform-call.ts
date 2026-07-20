import { getConnection, listConnections } from '@/lib/social/store'
import { getAvailableIntegrations } from '@/lib/integrations'

/**
 * Exécution d'appels sur les plateformes connectées PAR LE CLIENT.
 *
 * Sécurité (volontairement stricte) :
 * - LECTURE SEULE (GET) : on ne laisse pas le modèle écrire avec les clés du client
 *   (risque de paiement Stripe, suppression de données…). L'écriture nécessitera une
 *   confirmation explicite de l'utilisateur — non implémentée ici.
 * - HTTPS uniquement, hôte forcé à celui de la plateforme (pas d'URL absolue fournie
 *   par le modèle) → pas de SSRF.
 * - Timeout court et réponse tronquée.
 * - La clé n'est jamais renvoyée au modèle.
 */

type AuthMode = 'bearer' | 'header' | 'raw-authorization' | 'query'

interface PlatformSpec {
  baseUrl: string
  auth: AuthMode
  headerName?: string // pour 'header'
  queryName?: string // pour 'query'
  extraHeaders?: Record<string, string>
  /** Format du corps en écriture. Stripe n'accepte QUE du form-urlencoded. */
  bodyFormat?: 'json' | 'form'
}

/** Encode un objet en form-urlencoded façon Stripe (clés imbriquées : a[b]=c). */
function toFormBody(obj: unknown): URLSearchParams {
  const params = new URLSearchParams()
  const walk = (value: unknown, prefix: string) => {
    if (value === null || value === undefined) return
    if (Array.isArray(value)) {
      value.forEach((item, i) => walk(item, `${prefix}[${i}]`))
    } else if (typeof value === 'object') {
      for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
        walk(v, prefix ? `${prefix}[${k}]` : k)
      }
    } else {
      params.append(prefix, String(value))
    }
  }
  walk(obj, '')
  return params
}

// Bases d'API des plateformes du catalogue connectables par clé.
const PLATFORM_SPECS: Record<string, PlatformSpec> = {
  stripe: { baseUrl: 'https://api.stripe.com/v1', auth: 'bearer', bodyFormat: 'form' },
  hubspot: { baseUrl: 'https://api.hubapi.com', auth: 'bearer' },
  pennylane: { baseUrl: 'https://app.pennylane.com/api/external/v1', auth: 'bearer' },
  brevo: { baseUrl: 'https://api.brevo.com/v3', auth: 'header', headerName: 'api-key' },
  sendgrid: { baseUrl: 'https://api.sendgrid.com/v3', auth: 'bearer' },
  notion: {
    baseUrl: 'https://api.notion.com/v1',
    auth: 'bearer',
    extraHeaders: { 'Notion-Version': '2022-06-28' },
  },
  slack: { baseUrl: 'https://slack.com/api', auth: 'bearer' },
  calendly: { baseUrl: 'https://api.calendly.com', auth: 'bearer' },
  qonto: { baseUrl: 'https://thirdparty.qonto.com/v2', auth: 'raw-authorization' },
  pipedrive: { baseUrl: 'https://api.pipedrive.com/v1', auth: 'query', queryName: 'api_token' },
  asana: { baseUrl: 'https://app.asana.com/api/1.0', auth: 'bearer' },
  clickup: { baseUrl: 'https://api.clickup.com/api/v2', auth: 'raw-authorization' },
  monday: { baseUrl: 'https://api.monday.com/v2', auth: 'raw-authorization' },
  mollie: { baseUrl: 'https://api.mollie.com/v2', auth: 'bearer' },
  wise: { baseUrl: 'https://api.wise.com', auth: 'bearer' },
  zoho_books: { baseUrl: 'https://www.zohoapis.com/books/v3', auth: 'bearer' },
}

const CUSTOM_PREFIX = 'custom:'

/** Plateformes connectées par ce client, avec un libellé lisible. */
export async function listClientPlatforms(
  userId: string
): Promise<{ provider: string; name: string; readable: boolean }[]> {
  const rows = await listConnections(userId).catch(() => [])
  const catalog = getAvailableIntegrations()
  return rows.map((r) => {
    if (r.platform.startsWith(CUSTOM_PREFIX)) {
      let meta: { name?: string; baseUrl?: string } = {}
      try { meta = JSON.parse(r.external_id || '{}') } catch { /* ignore */ }
      return {
        provider: r.platform,
        name: meta.name || r.platform.slice(CUSTOM_PREFIX.length),
        readable: Boolean(meta.baseUrl),
      }
    }
    const item = catalog.find((c) => (c.id as string) === r.platform)
    return {
      provider: r.platform,
      name: item?.name || r.platform,
      readable: Boolean(PLATFORM_SPECS[r.platform]),
    }
  })
}

/** Résout la base d'API + le mode d'auth pour une connexion donnée. */
async function resolveSpec(
  userId: string,
  provider: string
): Promise<{ spec: PlatformSpec; secret: string } | { error: string }> {
  const conn = await getConnection(userId, provider).catch(() => null)
  if (!conn) return { error: `La plateforme "${provider}" n'est pas connectée par ce client.` }

  const secret = (conn as { access_token?: string }).access_token || ''
  if (!secret) return { error: `Aucun identifiant enregistré pour "${provider}".` }

  // WordPress : base = <site>/wp-json/wp/v2, auth Basic (utilisateur + mot de passe d'application).
  if (provider === 'wordpress') {
    let meta: { siteUrl?: string; user?: string } = {}
    try { meta = JSON.parse((conn as { external_id?: string }).external_id || '{}') } catch { /* ignore */ }
    if (!meta.siteUrl || !meta.user) {
      return { error: 'Configuration WordPress incomplète. Reconnectez le site dans Connexions.' }
    }
    const base = meta.siteUrl.replace(/\/$/, '') + '/wp-json/wp/v2'
    const basic = Buffer.from(`${meta.user}:${secret}`).toString('base64')
    return { spec: { baseUrl: base, auth: 'raw-authorization' }, secret: `Basic ${basic}` }
  }

  if (provider.startsWith(CUSTOM_PREFIX)) {
    let meta: { baseUrl?: string } = {}
    try { meta = JSON.parse((conn as { external_id?: string }).external_id || '{}') } catch { /* ignore */ }
    if (!meta.baseUrl) {
      return { error: `Aucune URL d'API enregistrée pour cette plateforme personnalisée. Demandez au client de la renseigner dans Connexions.` }
    }
    return { spec: { baseUrl: meta.baseUrl.replace(/\/$/, ''), auth: 'bearer' }, secret }
  }

  const spec = PLATFORM_SPECS[provider]
  if (!spec) return { error: `La lecture automatique n'est pas encore disponible pour "${provider}".` }
  return { spec, secret }
}

/**
 * Lit une ressource sur une plateforme connectée (GET uniquement).
 * `path` est un chemin relatif (ex : "/customers?limit=5"), jamais une URL absolue.
 */
export async function readFromPlatform(
  userId: string,
  provider: string,
  path: string
): Promise<{ ok: boolean; status?: number; data?: string; error?: string }> {
  const resolved = await resolveSpec(userId, provider)
  if ('error' in resolved) return { ok: false, error: resolved.error }
  const { spec, secret } = resolved

  // Chemin relatif obligatoire (anti-SSRF : l'hôte vient de NOTRE table, pas du modèle)
  const cleanPath = String(path || '/').trim()
  if (/^https?:\/\//i.test(cleanPath)) {
    return { ok: false, error: "Fournis un chemin relatif (ex : /customers?limit=5), pas une URL complète." }
  }

  let url: URL
  try {
    url = new URL(spec.baseUrl + (cleanPath.startsWith('/') ? cleanPath : `/${cleanPath}`))
  } catch {
    return { ok: false, error: 'Chemin invalide.' }
  }
  if (url.protocol !== 'https:') {
    return { ok: false, error: 'Seul HTTPS est autorisé.' }
  }

  const headers: Record<string, string> = { Accept: 'application/json', ...(spec.extraHeaders || {}) }
  if (spec.auth === 'bearer') headers.Authorization = `Bearer ${secret}`
  else if (spec.auth === 'raw-authorization') headers.Authorization = secret
  else if (spec.auth === 'header' && spec.headerName) headers[spec.headerName] = secret
  else if (spec.auth === 'query' && spec.queryName) url.searchParams.set(spec.queryName, secret)

  try {
    const res = await fetch(url.toString(), {
      method: 'GET',
      headers,
      signal: AbortSignal.timeout(10000),
    })
    const raw = await res.text()
    const data = raw.slice(0, 4000) // on borne la taille renvoyée au modèle
    if (!res.ok) {
      return { ok: false, status: res.status, error: `HTTP ${res.status} — ${data.slice(0, 300)}` }
    }
    return { ok: true, status: res.status, data }
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e)
    return { ok: false, error: msg.includes('timeout') ? 'Délai dépassé.' : msg }
  }
}

/**
 * Écriture sur une plateforme connectée (POST/PUT/PATCH/DELETE).
 * ⚠️ N'EST JAMAIS exposée au modèle : appelée uniquement par la route d'approbation,
 * après validation explicite de l'utilisateur.
 */
export async function writeToPlatform(
  userId: string,
  provider: string,
  method: string,
  path: string,
  body?: unknown
): Promise<{ ok: boolean; status?: number; data?: string; error?: string }> {
  const verb = String(method || '').toUpperCase()
  if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(verb)) {
    return { ok: false, error: `Méthode non autorisée : ${verb}` }
  }

  const resolved = await resolveSpec(userId, provider)
  if ('error' in resolved) return { ok: false, error: resolved.error }
  const { spec, secret } = resolved

  const cleanPath = String(path || '/').trim()
  if (/^https?:\/\//i.test(cleanPath)) {
    return { ok: false, error: 'Chemin relatif attendu, pas une URL complète.' }
  }

  let url: URL
  try {
    url = new URL(spec.baseUrl + (cleanPath.startsWith('/') ? cleanPath : `/${cleanPath}`))
  } catch {
    return { ok: false, error: 'Chemin invalide.' }
  }
  if (url.protocol !== 'https:') return { ok: false, error: 'Seul HTTPS est autorisé.' }

  const useForm = spec.bodyFormat === 'form'
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'Content-Type': useForm ? 'application/x-www-form-urlencoded' : 'application/json',
    ...(spec.extraHeaders || {}),
  }
  if (spec.auth === 'bearer') headers.Authorization = `Bearer ${secret}`
  else if (spec.auth === 'raw-authorization') headers.Authorization = secret
  else if (spec.auth === 'header' && spec.headerName) headers[spec.headerName] = secret
  else if (spec.auth === 'query' && spec.queryName) url.searchParams.set(spec.queryName, secret)

  const payload =
    body === undefined || body === null
      ? undefined
      : useForm
        ? toFormBody(body).toString()
        : JSON.stringify(body)

  try {
    const res = await fetch(url.toString(), {
      method: verb,
      headers,
      body: payload,
      signal: AbortSignal.timeout(15000),
    })
    const raw = await res.text()
    const data = raw.slice(0, 4000)
    if (!res.ok) return { ok: false, status: res.status, error: `HTTP ${res.status} — ${data.slice(0, 500)}` }
    return { ok: true, status: res.status, data }
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e)
    return { ok: false, error: msg.includes('timeout') ? 'Délai dépassé.' : msg }
  }
}

// ─── Définitions d'outils exposées aux agents ───────────────────────────────

export const listPlatformsTool = {
  name: 'lister_plateformes',
  description:
    "Liste les plateformes que CE client a connectées dans Bapica (compta, banque, CRM, e-commerce…). " +
    "Utilise-le avant lire_plateforme pour savoir de quelles données tu disposes réellement.",
  input_schema: { type: 'object' as const, properties: {}, required: [] as string[] },
}

export const proposeActionTool = {
  name: 'proposer_action',
  description:
    "PROPOSE une action qui MODIFIE des données sur une plateforme connectée (créer une facture, " +
    "envoyer un email, mettre à jour un contact…). Tu ne l'exécutes PAS : elle est mise en attente et " +
    "l'utilisateur doit la valider d'un clic dans « Actions à valider ». Après appel, dis simplement au " +
    "client que l'action est prête et attend sa validation. Rédige un résumé clair et précis (summary) : " +
    "c'est ce que l'utilisateur lira pour décider.",
  input_schema: {
    type: 'object' as const,
    properties: {
      provider: { type: 'string', description: 'Plateforme connectée cible (ex : stripe, pennylane)' },
      method: { type: 'string', enum: ['POST', 'PUT', 'PATCH', 'DELETE'], description: 'Méthode HTTP' },
      path: { type: 'string', description: "Chemin relatif de l'API, ex : /invoices" },
      body: { type: 'object', description: 'Corps de la requête (JSON)' },
      summary: { type: 'string', description: "Résumé lisible de l'action, présenté à l'utilisateur pour validation" },
    },
    required: ['provider', 'method', 'path', 'summary'],
  },
}

export const readPlatformTool = {
  name: 'lire_plateforme',
  description:
    "Lit des données réelles sur une plateforme connectée par le client (LECTURE SEULE). " +
    "Exemples : provider 'stripe' path '/customers?limit=5' ; provider 'pennylane' path '/customer_invoices' ; " +
    "provider 'qonto' path '/transactions'. Donne un chemin relatif à l'API, jamais une URL complète. " +
    "Aucune écriture n'est possible : pour créer ou modifier quelque chose, explique-le au client.",
  input_schema: {
    type: 'object' as const,
    properties: {
      provider: { type: 'string', description: "Identifiant de la plateforme connectée (ex : stripe, pennylane, qonto)" },
      path: { type: 'string', description: "Chemin relatif de l'API, ex : /customers?limit=5" },
    },
    required: ['provider', 'path'],
  },
}
