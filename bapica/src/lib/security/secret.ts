import { timingSafeEqual } from 'crypto'

/**
 * Comparaison de secrets à TEMPS CONSTANT (anti timing-attack). À utiliser pour comparer
 * un secret reçu (webhook, run d'automatisation) au secret attendu, plutôt que `===`.
 * Renvoie false si l'un est vide ou si les longueurs diffèrent.
 */
export function safeEqual(a: string | null | undefined, b: string | null | undefined): boolean {
  if (!a || !b) return false
  const ba = Buffer.from(a, 'utf8')
  const bb = Buffer.from(b, 'utf8')
  if (ba.length !== bb.length) return false
  return timingSafeEqual(ba, bb)
}
