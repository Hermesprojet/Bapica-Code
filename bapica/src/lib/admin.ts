/**
 * Liste d'administrateurs Bapica (accès aux insights produit).
 * `NEXT_PUBLIC_ADMIN_EMAILS` = emails séparés par des virgules. Lisible côté serveur ET
 * client (ce ne sont que des adresses, pas un secret). Vide = personne n'est admin.
 */
export function adminEmails(): string[] {
  return (process.env.NEXT_PUBLIC_ADMIN_EMAILS || '')
    .split(',')
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean)
}

export function isAdminEmail(email?: string | null): boolean {
  if (!email) return false
  return adminEmails().includes(email.toLowerCase())
}
