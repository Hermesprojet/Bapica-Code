import { NextRequest } from 'next/server'

/**
 * Rate-limiting partagé pour les endpoints publics (anti-abus / anti « DoS du portefeuille »
 * sur les routes qui appellent le LLM sans authentification).
 *
 * - Si UPSTASH_REDIS_REST_URL + UPSTASH_REDIS_REST_TOKEN sont configurés → compteur DISTRIBUÉ
 *   via Upstash Redis (REST, sans dépendance npm) : correct même avec plusieurs instances
 *   serverless.
 * - Sinon → repli MÉMOIRE (par instance, best-effort) : mieux que rien, mais non distribué.
 *
 * Dégrade toujours proprement : en cas d'indisponibilité du KV, on ne bloque pas le service.
 */

export function clientIp(req: NextRequest): string {
  const xff = req.headers.get('x-forwarded-for') || ''
  return xff.split(',')[0].trim() || req.headers.get('x-real-ip') || 'unknown'
}

const mem = new Map<string, { count: number; reset: number }>()

function memLimit(key: string, limit: number, windowMs: number): { ok: boolean; retryAfter: number } {
  const now = Date.now()
  const e = mem.get(key)
  if (!e || now >= e.reset) {
    mem.set(key, { count: 1, reset: now + windowMs })
    if (mem.size > 5000) for (const [k, v] of mem) if (now >= v.reset) mem.delete(k) // purge légère
    return { ok: true, retryAfter: 0 }
  }
  e.count++
  if (e.count > limit) return { ok: false, retryAfter: Math.ceil((e.reset - now) / 1000) }
  return { ok: true, retryAfter: 0 }
}

async function upstash(path: string): Promise<{ result?: unknown }> {
  const url = (process.env.UPSTASH_REDIS_REST_URL || '').replace(/\/$/, '')
  const res = await fetch(`${url}${path}`, {
    headers: { Authorization: `Bearer ${process.env.UPSTASH_REDIS_REST_TOKEN || ''}` },
    signal: AbortSignal.timeout(2000),
  })
  return res.json()
}

/**
 * Autorise `limit` requêtes par fenêtre de `windowSec` secondes pour une clé donnée.
 * Renvoie { ok, retryAfter } (retryAfter en secondes quand ok=false).
 */
export async function rateLimit(key: string, limit: number, windowSec: number): Promise<{ ok: boolean; retryAfter: number }> {
  const hasKv = process.env.UPSTASH_REDIS_REST_URL && process.env.UPSTASH_REDIS_REST_TOKEN
  if (!hasKv) return memLimit(key, limit, windowSec * 1000)
  try {
    const k = encodeURIComponent(`rl:${key}`)
    const incr = await upstash(`/incr/${k}`)
    const count = Number(incr.result)
    if (count === 1) await upstash(`/expire/${k}/${windowSec}`)
    if (count > limit) {
      const ttl = await upstash(`/ttl/${k}`)
      const t = Number((ttl as { result?: unknown }).result)
      return { ok: false, retryAfter: Math.max(1, Number.isFinite(t) && t > 0 ? t : windowSec) }
    }
    return { ok: true, retryAfter: 0 }
  } catch {
    return memLimit(key, limit, windowSec * 1000) // KV indisponible → repli, on ne bloque pas
  }
}
