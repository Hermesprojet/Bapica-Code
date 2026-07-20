import { getSupabaseAdmin } from '@/lib/supabase-admin'

// Actions proposées par les agents, en attente de validation humaine (table pending_actions).
// L'agent ne peut que PROPOSER ; l'exécution passe par l'approbation de l'utilisateur.

export type ActionStatus = 'pending' | 'executed' | 'rejected' | 'failed'

export interface PendingAction {
  id: string
  user_id: string
  agent_id: string | null
  provider: string
  method: string
  path: string
  body: unknown
  summary: string
  status: ActionStatus
  result: string | null
  created_at: string
  decided_at: string | null
}

function isMissingTable(error: { code?: string; message?: string } | null): boolean {
  return error?.code === '42P01' || /pending_actions.*does not exist/i.test(error?.message || '')
}

export async function createAction(input: {
  userId: string
  agentId?: string
  provider: string
  method: string
  path: string
  body?: unknown
  summary: string
}): Promise<string> {
  const db = getSupabaseAdmin()
  const { data, error } = await db
    .from('pending_actions')
    .insert({
      user_id: input.userId,
      agent_id: input.agentId ?? null,
      provider: input.provider,
      method: input.method.toUpperCase(),
      path: input.path,
      body: (input.body ?? null) as never,
      summary: input.summary,
      status: 'pending',
    })
    .select('id')
    .single()

  if (error) {
    if (isMissingTable(error)) throw new Error('ACTIONS_TABLE_MISSING')
    throw new Error(`Création de l'action : ${error.message}`)
  }
  return (data as { id: string }).id
}

export async function listActions(userId: string, status?: ActionStatus): Promise<PendingAction[]> {
  const db = getSupabaseAdmin()
  let q = db.from('pending_actions').select('*').eq('user_id', userId).order('created_at', { ascending: false }).limit(50)
  if (status) q = q.eq('status', status)
  const { data, error } = await q
  if (error) {
    // Distinguer « pas d'actions » de « table absente » (SQL non exécuté).
    if (isMissingTable(error)) throw new Error('ACTIONS_TABLE_MISSING')
    return []
  }
  return (data as PendingAction[]) || []
}

export async function getAction(userId: string, id: string): Promise<PendingAction | null> {
  const db = getSupabaseAdmin()
  const { data } = await db.from('pending_actions').select('*').eq('user_id', userId).eq('id', id).maybeSingle()
  return (data as PendingAction) || null
}

export async function markAction(
  id: string,
  status: ActionStatus,
  result?: string
): Promise<void> {
  const db = getSupabaseAdmin()
  await db
    .from('pending_actions')
    .update({ status, result: result ?? null, decided_at: new Date().toISOString() })
    .eq('id', id)
}
