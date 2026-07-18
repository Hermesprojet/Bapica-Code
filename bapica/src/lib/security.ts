/**
 * Utilitaires de sécurité pour Bapica
 * - Sanitization XSS
 * - Validation d'entrées
 */

/**
 * Échapper les caractères HTML spéciaux (sûr côté serveur et client)
 */
export function escapeHtml(input: string): string {
  if (!input || typeof input !== 'string') return ''
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#x27;',
    '/': '&#x2F;',
  }
  return input.replace(/[&<>"'/]/g, c => map[c] || c)
}

/**
 * Sanitize une chaîne (supprime tous les tags HTML)
 */
export function sanitize(input: string): string {
  if (!input || typeof input !== 'string') return ''
  // Remove HTML tags
  return input.replace(/<[^>]*>/g, '')
}

/**
 * Valider un email
 */
export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

/**
 * Valider et tronquer un message utilisateur
 */
export function sanitizeUserMessage(input: string, maxLength = 4000): string {
  if (!input || typeof input !== 'string') return ''
  const trimmed = input.trim().slice(0, maxLength)
  return sanitize(trimmed)
}

/**
 * Valider un agentId (liste blanche — protection contre injection)
 */
const VALID_AGENT_IDS = new Set([
  'general', 'support', 'content', 'prospection-strategie', 'closer',
  'telephone', 'accounting', 'video', 'recruiter', 'legal',
])

export function isValidAgentId(id: string): boolean {
  return VALID_AGENT_IDS.has(id)
}
