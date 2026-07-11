/**
 * Bapica Universal Connector
 * 
 * Se connecte à N'IMPORTE QUEL SaaS, Cloud ou plateforme.
 * Pas de liste fixe — le système découvre, s'adapte et apprend.
 * 
 * Architecture:
 * 1. Discovery — scan automatique (OpenAPI, Swagger, introspection)
 * 2. Auth Orchestrator — OAuth2, API Key, JWT, Basic auto-détectés
 * 3. Proxy Adaptatif — middleware chain configurable
 * 4. Normalisation Sémantique — ontologie commune
 * 5. Webhook Inbox Universel — un seul endpoint, tous les webhooks
 * 6. Sandbox Learning — apprend par exemples (copier-coller Postman)
 */

// ─── TYPES ─────────────────────────────────────────────────

export interface UniversalConnector {
  name: string
  baseUrl: string
  protocol: 'REST' | 'GraphQL' | 'SOAP' | 'gRPC' | 'WebSocket'
  auth: {
    type: 'oauth2' | 'api_key' | 'jwt' | 'basic' | 'none'
    config: Record<string, string>
  }
  endpoints: DiscoveredEndpoint[]
  schema: Record<string, any>
  mapping: SemanticMapping[]
}

export interface DiscoveredEndpoint {
  path: string
  method: string
  description: string
  params: Record<string, any>
  returns: string
  tested: boolean
  working: boolean
}

export interface SemanticMapping {
  externalField: string
  internalConcept: string
  confidence: number
  examples: string[]
}

// ─── DISCOVERY ENGINE ──────────────────────────────────────

/**
 * Tente de découvrir automatiquement la structure d'un SaaS
 * en scannant les endpoints standards de documentation.
 */
export async function discoverPlatform(baseUrl: string): Promise<Partial<UniversalConnector>> {
  const discovery: Partial<UniversalConnector> = {
    name: new URL(baseUrl).hostname,
    baseUrl,
    endpoints: [],
    protocol: 'REST',
  }

  const paths = [
    '/openapi.json',
    '/api-docs',
    '/swagger.json',
    '/.well-known/ai-plugin.json',
    '/api/schema',
    '/docs/api',
    '/api/v1/openapi.json',
  ]

  for (const path of paths) {
    try {
      const res = await fetch(`${baseUrl}${path}`, { signal: AbortSignal.timeout(5000) })
      if (!res.ok) continue

      const text = await res.text()

      // OpenAPI / Swagger détecté
      if (text.includes('"openapi"') || text.includes('"swagger"')) {
        const spec = JSON.parse(text)
        discovery.endpoints = parseOpenAPI(spec, baseUrl)
        discovery.name = spec.info?.title || discovery.name
        discovery.protocol = 'REST'
        break
      }

      // GraphQL introspecté
      if (path.includes('graphql') && text.includes('__schema')) {
        discovery.protocol = 'GraphQL'
        break
      }
    } catch {}
  }

  return discovery
}

function parseOpenAPI(spec: any, baseUrl: string): DiscoveredEndpoint[] {
  const endpoints: DiscoveredEndpoint[] = []
  const paths = spec.paths || {}

  for (const [path, methods] of Object.entries(paths) as [string, any][]) {
    for (const [method, rawDetails] of Object.entries(methods)) {
      if (!['get', 'post', 'put', 'patch', 'delete'].includes(method)) continue
      const d = rawDetails as any
      endpoints.push({
        path: `${baseUrl}${path}`,
        method: method.toUpperCase(),
        description: d.summary || d.description || '',
        params: d.parameters || {},
        returns: d.responses?.['200']?.description || '',
        tested: false,
        working: false,
      })
    }
  }
  return endpoints
}

// ─── AUTH ORCHESTRATOR ─────────────────────────────────────

/**
 * Détecte et négocie automatiquement l'authentification
 */
export async function detectAuth(baseUrl: string): Promise<UniversalConnector['auth']> {
  // Test 1: Pas d'auth
  try {
    const r = await fetch(baseUrl, { signal: AbortSignal.timeout(3000) })
    if (r.ok) return { type: 'none', config: {} }
  } catch {}

  // Test 2: API Key dans header commun
  const commonHeaders = ['X-API-Key', 'Authorization', 'api-key', 'apikey']
  for (const h of commonHeaders) {
    try {
      const r = await fetch(baseUrl, {
        headers: { [h]: 'test' },
        signal: AbortSignal.timeout(3000),
      })
      if (r.status === 401) return { type: 'api_key', config: { header: h } }
      if (r.status === 403) return { type: 'api_key', config: { header: h } }
    } catch {}
  }

  // Test 3: OAuth2 — chercher les endpoints standards
  const oauthPaths = ['/oauth/authorize', '/oauth/token', '/auth/oauth', '/connect/authorize']
  for (const path of oauthPaths) {
    try {
      const r = await fetch(`${baseUrl}${path}`, { signal: AbortSignal.timeout(3000) })
      if (r.status < 500) return {
        type: 'oauth2',
        config: { authorizeUrl: `${baseUrl}${path}`, tokenUrl: `${baseUrl}${path.replace('authorize', 'token')}` }
      }
    } catch {}
  }

  return { type: 'api_key', config: {} }
}

// ─── SANDBOX LEARNING ──────────────────────────────────────

/**
 * Apprend par exemples : l'utilisateur copie-colle une requête depuis Postman/Bruno
 * et Bapica en extrait la structure.
 */
export function learnFromExample(rawRequest: string): {
  method: string
  url: string
  headers: Record<string, string>
  body: any
  response: any
} | null {
  try {
    // Format Postman: "GET https://api.example.com/users"
    const lines = rawRequest.trim().split('\n')
    const firstLine = lines[0]
    const [method, url] = firstLine.split(/\s+/, 2)

    const headers: Record<string, string> = {}
    let bodyStart = 0

    for (let i = 1; i < lines.length; i++) {
      if (!lines[i].trim()) { bodyStart = i + 1; break }
      const [k, v] = lines[i].split(/:\s*/, 2)
      if (k && v) headers[k.trim()] = v.trim()
    }

    const body = bodyStart > 0 ? lines.slice(bodyStart).join('\n') : null

    return {
      method: method.toUpperCase(),
      url,
      headers,
      body: body ? JSON.parse(body) : null,
      response: {},
    }
  } catch {
    return null
  }
}

// ─── WEBHOOK INBOX UNIVERSEL ───────────────────────────────

/**
 * Un seul endpoint reçoit TOUS les webhooks.
 * L'IA analyse le payload et le route vers le bon agent.
 */
export interface UniversalWebhook {
  id: string
  source: string
  event: string
  payload: any
  receivedAt: string
  routedTo: string
  confidence: number
}

const webhookPatterns: Record<string, { keywords: string[]; agent: string }> = {
  stripe: { keywords: ['invoice', 'payment', 'subscription', 'charge'], agent: 'accounting' },
  github: { keywords: ['push', 'pull_request', 'commit', 'repository'], agent: 'general' },
  gmail: { keywords: ['message', 'email', 'thread'], agent: 'support' },
  hubspot: { keywords: ['contact', 'deal', 'company', 'pipeline'], agent: 'prospection-strategie' },
  calendly: { keywords: ['event', 'invitee', 'scheduled', 'canceled'], agent: 'general' },
  shopify: { keywords: ['order', 'product', 'customer', 'checkout'], agent: 'prospection-strategie' },
  payfit: { keywords: ['employee', 'payslip', 'leave'], agent: 'recruiter' },
  zendesk: { keywords: ['ticket', 'comment', 'status'], agent: 'support' },
  slack: { keywords: ['message', 'channel', 'reaction'], agent: 'general' },
}

export function routeWebhook(payload: any): { agent: string; confidence: number } {
  const jsonStr = JSON.stringify(payload).toLowerCase()
  let bestAgent = 'general'
  let bestScore = 0

  for (const [source, config] of Object.entries(webhookPatterns)) {
    let score = 0
    for (const kw of config.keywords) {
      if (jsonStr.includes(kw)) score++
    }
    const normalized = score / config.keywords.length
    if (normalized > bestScore) {
      bestScore = normalized
      bestAgent = config.agent
    }
  }

  return { agent: bestAgent, confidence: bestScore }
}

// ─── NORMALISATION SÉMANTIQUE ──────────────────────────────

/**
 * Concepts universels que Bapica comprend.
 * Chaque SaaS externe est mappé vers cette ontologie.
 */
export const UNIVERSAL_CONCEPTS: Record<string, { fields: string[]; synonyms: string[] }> = {
  client: { fields: ['id', 'name', 'email', 'phone', 'company'], synonyms: ['customer', 'contact', 'lead', 'account', 'cliente'] },
  facture: { fields: ['id', 'amount', 'date', 'status', 'items'], synonyms: ['invoice', 'bill', 'receipt', 'fattura', 'factura'] },
  paiement: { fields: ['id', 'amount', 'date', 'method', 'status'], synonyms: ['payment', 'transaction', 'charge', 'pago'] },
  produit: { fields: ['id', 'name', 'price', 'description', 'sku'], synonyms: ['product', 'item', 'article', 'producto', 'servicio'] },
  commande: { fields: ['id', 'client_id', 'total', 'status', 'items'], synonyms: ['order', 'purchase', 'commande', 'pedido'] },
  employe: { fields: ['id', 'name', 'email', 'role', 'salary'], synonyms: ['employee', 'staff', 'worker', 'collaborateur'] },
  ticket: { fields: ['id', 'subject', 'status', 'priority', 'assignee'], synonyms: ['issue', 'request', 'case', 'ticket'] },
  rencontre: { fields: ['id', 'date', 'duration', 'participants', 'notes'], synonyms: ['meeting', 'event', 'appointment', 'rendezvous'] },
  projet: { fields: ['id', 'name', 'status', 'tasks', 'deadline'], synonyms: ['project', 'board', 'initiative', 'sprint'] },
  document: { fields: ['id', 'title', 'content', 'author', 'created'], synonyms: ['file', 'note', 'page', 'doc'] },
}

/**
 * Mapper un champ externe vers un concept Bapica
 */
export function mapToConcept(externalField: string): { concept: string; confidence: number } | null {
  const field = externalField.toLowerCase()

  for (const [concept, { synonyms }] of Object.entries(UNIVERSAL_CONCEPTS)) {
    for (const syn of synonyms) {
      if (field.includes(syn)) {
        return { concept, confidence: field === syn ? 0.9 : 0.6 }
      }
    }
  }

  return null
}

// ─── MARKETPLACE DE MICRO-CONNECTEURS ──────────────────────

/**
 * Format déclaratif d'un connecteur (pas de code exécutable)
 */
export interface MicroConnector {
  name: string
  version: string
  baseUrl: string
  auth: {
    type: string
    fields: { name: string; label: string; placeholder: string }[]
  }
  endpoints: {
    name: string
    path: string
    method: string
    description: string
  }[]
  author: string
  rating: number
  downloads: number
}

// Registry partagée (locale pour l'instant, future DB communautaire)
const marketplaceRegistry: MicroConnector[] = []

export function registerConnector(connector: MicroConnector) {
  const existing = marketplaceRegistry.findIndex(c => c.name === connector.name && c.baseUrl === connector.baseUrl)
  if (existing >= 0) {
    marketplaceRegistry[existing] = connector
  } else {
    marketplaceRegistry.push(connector)
  }
}

export function searchConnectors(query: string): MicroConnector[] {
  const q = query.toLowerCase()
  return marketplaceRegistry.filter(c =>
    c.name.toLowerCase().includes(q) ||
    c.endpoints.some(e => e.name.toLowerCase().includes(q))
  ).sort((a, b) => b.downloads - a.downloads)
}

export function getConnector(name: string, baseUrl: string): MicroConnector | undefined {
  return marketplaceRegistry.find(c => c.name === name && c.baseUrl === baseUrl)
}
