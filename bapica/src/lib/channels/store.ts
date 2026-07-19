import { getSupabaseAdmin } from '@/lib/supabase-admin'

// Stockage serveur des connexions de messagerie par client (table channel_connections).
// Voir supabase-schema.sql. Accès service_role uniquement (RLS sans policy).

export interface ChannelConnectionInput {
  credentials: Record<string, unknown> // telegram : { botToken } ; whatsapp : { ... }
  externalId?: string | null // telegram : bot username ; whatsapp : numéro E.164
  webhookSecret?: string | null
  status?: string
}

export interface ChannelConnection {
  id: string
  user_id: string
  platform: string
  credentials: Record<string, unknown>
  external_id: string | null
  webhook_secret: string | null
  status: string
}

// La table n'existe pas encore (supabase-schema.sql non exécuté) → code Postgres 42P01.
function isMissingTable(error: { code?: string; message?: string } | null): boolean {
  return error?.code === '42P01' || /channel_connections.*does not exist/i.test(error?.message || '')
}

export async function saveChannel(userId: string, platform: string, c: ChannelConnectionInput): Promise<void> {
  const db = getSupabaseAdmin()
  const { error } = await db.from('channel_connections').upsert(
    {
      user_id: userId,
      platform,
      credentials: c.credentials,
      external_id: c.externalId ?? null,
      webhook_secret: c.webhookSecret ?? null,
      status: c.status ?? 'connected',
      updated_at: new Date().toISOString(),
    },
    { onConflict: 'user_id,platform' }
  )
  if (error) {
    if (isMissingTable(error)) throw new Error('CHANNELS_TABLE_MISSING')
    throw new Error(`Enregistrement du canal : ${error.message}`)
  }
}

export async function getChannel(userId: string, platform: string): Promise<ChannelConnection | null> {
  const db = getSupabaseAdmin()
  const { data, error } = await db.from('channel_connections').select('*').eq('user_id', userId).eq('platform', platform).maybeSingle()
  if (error && isMissingTable(error)) throw new Error('CHANNELS_TABLE_MISSING')
  return (data as ChannelConnection) || null
}

export async function getChannelBySecret(secret: string): Promise<ChannelConnection | null> {
  if (!secret) return null
  const db = getSupabaseAdmin()
  const { data, error } = await db.from('channel_connections').select('*').eq('webhook_secret', secret).maybeSingle()
  if (error) return null
  return (data as ChannelConnection) || null
}

export async function getChannelByExternal(platform: string, externalId: string): Promise<ChannelConnection | null> {
  if (!externalId) return null
  const db = getSupabaseAdmin()
  const { data, error } = await db.from('channel_connections').select('*').eq('platform', platform).eq('external_id', externalId).maybeSingle()
  if (error) return null
  return (data as ChannelConnection) || null
}

export async function listChannels(userId: string): Promise<ChannelConnection[]> {
  const db = getSupabaseAdmin()
  const { data, error } = await db.from('channel_connections').select('*').eq('user_id', userId)
  if (error) return []
  return (data as ChannelConnection[]) || []
}

export async function deleteChannel(userId: string, platform: string): Promise<void> {
  const db = getSupabaseAdmin()
  await db.from('channel_connections').delete().eq('user_id', userId).eq('platform', platform)
}
