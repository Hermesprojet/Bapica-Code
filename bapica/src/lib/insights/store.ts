import { getSupabaseAdmin } from '@/lib/supabase-admin'

// Signaux d'expérience client (table client_signals). Écriture « best-effort » :
// une capture qui échoue ne doit jamais casser le flux utilisateur.

export type SignalType = 'question' | 'feedback' | 'action_failed'

export interface ClientSignal {
  id: string
  user_id: string | null
  type: SignalType
  content: string
  meta: Record<string, unknown>
  created_at: string
}

export async function logSignal(
  type: SignalType,
  content: string,
  opts?: { userId?: string; meta?: Record<string, unknown> }
): Promise<void> {
  if (!content?.trim()) return
  try {
    const db = getSupabaseAdmin()
    await db.from('client_signals').insert({
      user_id: opts?.userId ?? null,
      type,
      content: content.slice(0, 2000),
      meta: (opts?.meta ?? {}) as never,
    })
  } catch {
    /* best-effort : on n'interrompt jamais l'utilisateur */
  }
}

export async function listSignals(limitPerType = 200): Promise<ClientSignal[]> {
  const db = getSupabaseAdmin()
  const { data, error } = await db
    .from('client_signals')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(limitPerType)
  if (error) {
    if (error.code === '42P01') throw new Error('SIGNALS_TABLE_MISSING')
    return []
  }
  return (data as ClientSignal[]) || []
}
