import { getSupabaseAdmin } from '@/lib/supabase-admin'

// Étiquettes d'échanges (table interaction_tags) — prospect intéressé, SAV, impayé…
// Accès service_role uniquement (RLS activée sans policy).

export const TAG_VALUES = [
  'prospect_interesse',
  'rappel_demande',
  'sav',
  'impaye',
  'pas_interesse',
  'autre',
] as const
export type TagValue = (typeof TAG_VALUES)[number]

export const TAG_LABELS: Record<TagValue, string> = {
  prospect_interesse: 'Prospect intéressé',
  rappel_demande: 'Rappel demandé',
  sav: 'SAV',
  impaye: 'Impayé',
  pas_interesse: 'Pas intéressé',
  autre: 'Autre',
}

export interface TagRow {
  id: string
  user_id: string
  agent_id: string | null
  channel: string | null
  contact: string | null
  tag: string
  note: string | null
  created_at: string
}

function isMissingTable(error: { code?: string; message?: string } | null): boolean {
  return error?.code === '42P01' || /interaction_tags.*does not exist/i.test(error?.message || '')
}

export function normalizeTag(tag: string): TagValue {
  return (TAG_VALUES as readonly string[]).includes(tag) ? (tag as TagValue) : 'autre'
}

export async function createTag(input: {
  userId: string
  agentId?: string
  channel?: string
  contact?: string
  tag: string
  note?: string
}): Promise<string> {
  const db = getSupabaseAdmin()
  const { data, error } = await db
    .from('interaction_tags')
    .insert({
      user_id: input.userId,
      agent_id: input.agentId ?? null,
      channel: input.channel ?? null,
      contact: input.contact ?? null,
      tag: normalizeTag(input.tag),
      note: input.note ?? null,
    })
    .select('id')
    .single()
  if (error) {
    if (isMissingTable(error)) throw new Error('TAGS_TABLE_MISSING')
    throw new Error(`Création de l'étiquette : ${error.message}`)
  }
  return (data as { id: string }).id
}

export async function listTags(userId: string, tag?: string): Promise<TagRow[]> {
  const db = getSupabaseAdmin()
  let q = db.from('interaction_tags').select('*').eq('user_id', userId).order('created_at', { ascending: false }).limit(200)
  if (tag && (TAG_VALUES as readonly string[]).includes(tag)) q = q.eq('tag', tag)
  const { data, error } = await q
  if (error) {
    if (isMissingTable(error)) throw new Error('TAGS_TABLE_MISSING')
    return []
  }
  return (data as TagRow[]) || []
}

export async function deleteTag(userId: string, id: string): Promise<void> {
  const db = getSupabaseAdmin()
  await db.from('interaction_tags').delete().eq('user_id', userId).eq('id', id)
}
