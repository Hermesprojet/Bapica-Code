import { getSupabaseAdmin } from '@/lib/supabase-admin'

// Documents produits par les agents (table deliverables) — accès service_role uniquement.

export interface DeliverableRow {
  id: string
  user_id: string
  agent_id: string | null
  kind: string
  title: string
  filename: string
  mime: string
  content: string
  created_at: string
}

function isMissingTable(error: { code?: string; message?: string } | null): boolean {
  return error?.code === '42P01' || /deliverables.*does not exist/i.test(error?.message || '')
}

export async function createDeliverable(input: {
  userId: string
  agentId?: string
  kind: string
  title: string
  filename: string
  mime: string
  content: string
}): Promise<string> {
  const db = getSupabaseAdmin()
  const { data, error } = await db
    .from('deliverables')
    .insert({
      user_id: input.userId,
      agent_id: input.agentId ?? null,
      kind: input.kind,
      title: input.title,
      filename: input.filename,
      mime: input.mime,
      content: input.content,
    })
    .select('id')
    .single()
  if (error) {
    if (isMissingTable(error)) throw new Error('DELIVERABLES_TABLE_MISSING')
    throw new Error(`Création du document : ${error.message}`)
  }
  return (data as { id: string }).id
}

/** Liste les documents (sans le contenu, pour alléger). */
export async function listDeliverables(userId: string): Promise<Omit<DeliverableRow, 'content'>[]> {
  const db = getSupabaseAdmin()
  const { data, error } = await db
    .from('deliverables')
    .select('id, user_id, agent_id, kind, title, filename, mime, created_at')
    .eq('user_id', userId)
    .order('created_at', { ascending: false })
    .limit(100)
  if (error) {
    if (isMissingTable(error)) throw new Error('DELIVERABLES_TABLE_MISSING')
    return []
  }
  return (data as Omit<DeliverableRow, 'content'>[]) || []
}

export async function getDeliverable(userId: string, id: string): Promise<DeliverableRow | null> {
  const db = getSupabaseAdmin()
  const { data } = await db.from('deliverables').select('*').eq('user_id', userId).eq('id', id).maybeSingle()
  return (data as DeliverableRow) || null
}

export async function deleteDeliverable(userId: string, id: string): Promise<void> {
  const db = getSupabaseAdmin()
  await db.from('deliverables').delete().eq('user_id', userId).eq('id', id)
}
