import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { isAdminEmail } from '@/lib/admin'
import { checkEnv } from '@/lib/env'

/**
 * GET /api/health/env — bilan des variables d'environnement configurées en prod.
 *
 * Réservé aux administrateurs (`NEXT_PUBLIC_ADMIN_EMAILS`). Ne renvoie JAMAIS la valeur
 * d'une variable : uniquement des booléens de présence et les noms manquants — utile
 * après un déploiement pour vérifier ce qui reste à renseigner dans Vercel.
 */
export async function GET(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) {
    return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  }
  if (!isAdminEmail(user.email)) {
    return NextResponse.json({ error: 'Réservé aux administrateurs' }, { status: 403 })
  }

  const report = checkEnv()
  return NextResponse.json(report)
}
