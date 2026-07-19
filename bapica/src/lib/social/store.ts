import { getSupabaseAdmin } from '@/lib/supabase-admin'

// Stockage serveur des connexions réseaux sociaux (table social_connections).
// Voir supabase-schema.sql pour la définition de la table.

export interface SocialConnectionInput {
  accessToken: string
  refreshToken?: string | null
  expiresAt?: string | null   // ISO
  externalId?: string | null  // ex : sub LinkedIn (member id)
}

export async function saveConnection(userId: string, platform: string, c: SocialConnectionInput): Promise<void> {
  const db = getSupabaseAdmin()
  const { error } = await db.from('social_connections').upsert(
    {
      user_id: userId,
      platform,
      access_token: c.accessToken,
      refresh_token: c.refreshToken ?? null,
      expires_at: c.expiresAt ?? null,
      external_id: c.externalId ?? null,
      updated_at: new Date().toISOString(),
    },
    { onConflict: 'user_id,platform' }
  )
  if (error) throw new Error(`Enregistrement connexion : ${error.message}`)
}

export async function getConnection(userId: string, platform: string) {
  const db = getSupabaseAdmin()
  const { data } = await db.from('social_connections').select('*').eq('user_id', userId).eq('platform', platform).maybeSingle()
  return data
}

/** Liste complète (plateforme + métadonnées) — utilisé pour les plateformes personnalisées. */
export async function listConnections(userId: string): Promise<{ platform: string; external_id: string | null }[]> {
  const db = getSupabaseAdmin()
  const { data } = await db.from('social_connections').select('platform, external_id').eq('user_id', userId)
  return (data as { platform: string; external_id: string | null }[]) || []
}

export async function listPlatforms(userId: string): Promise<string[]> {
  const db = getSupabaseAdmin()
  const { data } = await db.from('social_connections').select('platform').eq('user_id', userId)
  return (data || []).map((r: { platform: string }) => r.platform)
}

export async function deleteConnection(userId: string, platform: string): Promise<void> {
  const db = getSupabaseAdmin()
  await db.from('social_connections').delete().eq('user_id', userId).eq('platform', platform)
}
