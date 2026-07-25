import { lookup } from 'dns/promises'
import net from 'net'

/**
 * Garde anti-SSRF. À appeler AVANT tout fetch d'une URL fournie par l'utilisateur ou
 * choisie par le modèle (audit SEO, analyse d'entreprise…). Refuse :
 *  - les schémas autres que http(s) (bloque file://, gopher://…) ;
 *  - les hôtes locaux (localhost, *.local, *.internal) ;
 *  - toute IP privée / loopback / link-local / réservée, y compris APRÈS résolution DNS
 *    (un domaine public peut pointer vers 127.0.0.1 ou 169.254.169.254 — métadonnées cloud).
 * Nécessite le runtime Node (dns) — les appelants tournent déjà côté serveur.
 */

function isPrivateIp(ip: string): boolean {
  if (net.isIPv4(ip)) {
    const [a, b] = ip.split('.').map(Number)
    if (a === 10 || a === 127 || a === 0) return true
    if (a === 169 && b === 254) return true // link-local + métadonnées cloud (169.254.169.254)
    if (a === 172 && b >= 16 && b <= 31) return true
    if (a === 192 && b === 168) return true
    if (a === 100 && b >= 64 && b <= 127) return true // CGNAT
    if (a >= 224) return true // multicast / réservé
    return false
  }
  if (net.isIPv6(ip)) {
    const v = ip.toLowerCase()
    if (v === '::1' || v === '::') return true
    if (v.startsWith('fc') || v.startsWith('fd')) return true // unique-local
    if (v.startsWith('fe80')) return true // link-local
    if (v.startsWith('::ffff:')) return isPrivateIp(v.slice(7)) // IPv4-mappée
    return false
  }
  return true // format inconnu → on refuse par prudence
}

/** Valide l'URL et renvoie l'objet URL sûr, ou lève une erreur explicite. */
export async function assertPublicUrl(raw: string): Promise<URL> {
  let parsed: URL
  try {
    parsed = new URL(raw)
  } catch {
    throw new Error('URL invalide.')
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    throw new Error('Seuls les liens http(s) sont autorisés.')
  }
  const host = parsed.hostname.toLowerCase().replace(/^\[|\]$/g, '')
  if (host === 'localhost' || host.endsWith('.localhost') || host.endsWith('.local') || host.endsWith('.internal')) {
    throw new Error('Hôte interne non autorisé.')
  }
  const literalIp = net.isIP(host) ? host : null
  const ips = literalIp ? [literalIp] : (await lookup(host, { all: true }).catch(() => [])).map((r) => r.address)
  if (!ips.length || ips.some(isPrivateIp)) {
    throw new Error('Adresse réseau interne non autorisée.')
  }
  return parsed
}
