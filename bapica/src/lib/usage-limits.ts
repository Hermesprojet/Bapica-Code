/**
 * Compteur d'usage unifié pour Bapica
 * 
 * Tracke la consommation par utilisateur : vidéos, appels, tokens IA, analyses.
 * Quotas alignés sur les plans Essentiel (49€) et Pro (79€).
 */

import { createClient } from '@supabase/supabase-js'

export interface UsageQuota {
  /** Vidéos générées (HeyGen, Runway, ElevenLabs) */
  videos: number
  /** Appels téléphoniques (Vapi) */
  calls: number
  /** Minutes d'appels consommées */
  callMinutes: number
  /** Tokens IA consommés (entrée + sortie) */
  tokensIn: number
  tokensOut: number
  /** Analyses business générées */
  analyses: number
  /** Contact forms submitted */
  contacts: number
}

export const QUOTA_LIMITS: Record<string, UsageQuota> = {
  essential: {
    videos: 3,
    calls: 50,
    callMinutes: 100,
    tokensIn: 500_000,
    tokensOut: 200_000,
    analyses: 20,
    contacts: 100,
  },
  pro: {
    videos: 20,
    calls: 200,
    callMinutes: 500,
    tokensIn: 2_000_000,
    tokensOut: 1_000_000,
    analyses: 100,
    contacts: 500,
  },
}

/**
 * Récupère l'usage courant d'un utilisateur pour le mois en cours
 */
export async function getCurrentUsage(userId: string): Promise<UsageQuota> {
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL || '',
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''
  )

  const startOfMonth = new Date()
  startOfMonth.setDate(1)
  startOfMonth.setHours(0, 0, 0, 0)

  const { data, error } = await supabase
    .from('usage_logs')
    .select('type, value')
    .eq('user_id', userId)
    .gte('created_at', startOfMonth.toISOString())

  if (error) return { videos: 0, calls: 0, callMinutes: 0, tokensIn: 0, tokensOut: 0, analyses: 0, contacts: 0 }

  const usage: UsageQuota = { videos: 0, calls: 0, callMinutes: 0, tokensIn: 0, tokensOut: 0, analyses: 0, contacts: 0 }
  
  for (const row of data || []) {
    const t = row.type as keyof UsageQuota
    if (t in usage) (usage[t] as number) += row.value || 1
  }

  return usage
}

/**
 * Vérifie si une action est autorisée (sous le quota)
 */
export function isWithinQuota(usage: UsageQuota, plan: string, action: keyof UsageQuota): boolean {
  const limits = QUOTA_LIMITS[plan] || QUOTA_LIMITS.essential
  return usage[action] < limits[action]
}

/**
 * Log une consommation
 */
export async function logUsage(userId: string, type: keyof UsageQuota, value: number = 1) {
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL || '',
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''
  )

  await supabase.from('usage_logs').insert({
    user_id: userId,
    type,
    value,
    created_at: new Date().toISOString(),
  })
}

/**
 * Retourne le % de quota utilisé (pour afficher une barre de progression)
 */
export function getUsagePercent(usage: UsageQuota, plan: string, action: keyof UsageQuota): number {
  const limits = QUOTA_LIMITS[plan] || QUOTA_LIMITS.essential
  const used = usage[action]
  const limit = limits[action]
  if (limit === 0) return 0
  return Math.min(100, Math.round((used / limit) * 100))
}

/**
 * Retourne un message d'erreur si dépassement
 */
export function getQuotaMessage(usage: UsageQuota, plan: string, action: keyof UsageQuota): string | null {
  if (isWithinQuota(usage, plan, action)) return null
  const limits = QUOTA_LIMITS[plan] || QUOTA_LIMITS.essential
  const labels: Record<keyof UsageQuota, string> = {
    videos: 'vidéos',
    calls: 'appels',
    callMinutes: 'minutes d\'appel',
    tokensIn: 'tokens IA',
    tokensOut: 'tokens IA',
    analyses: 'analyses',
    contacts: 'formulaires',
  }
  return `Quota ${labels[action]} dépassé (${usage[action]}/${limits[action]}). Passez au plan Pro pour plus.`
}
