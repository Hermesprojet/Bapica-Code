import { getSupabaseAdmin } from '@/lib/supabase-admin'

// Relances d'impayés programmées (table payment_reminders) — échéancier J+7/J+15/J+30.
// Accès service_role uniquement (RLS activée sans policy).

export type ReminderStage = 'amiable' | 'ferme' | 'mise_en_demeure'
export type ReminderStatus = 'scheduled' | 'sent' | 'cancelled' | 'paid'

export interface ReminderRow {
  id: string
  user_id: string
  client: string
  contact_email: string | null
  invoice_ref: string | null
  amount: number | null
  currency: string | null
  stage: string
  due_on: string
  subject: string | null
  body: string | null
  status: string
  created_at: string
  sent_at: string | null
}

function isMissingTable(error: { code?: string; message?: string } | null): boolean {
  return error?.code === '42P01' || /payment_reminders.*does not exist/i.test(error?.message || '')
}

const STAGES: ReminderStage[] = ['amiable', 'ferme', 'mise_en_demeure']

/** Crée une série de relances programmées (offset en jours à partir d'aujourd'hui). */
export async function createReminders(input: {
  userId: string
  client: string
  contactEmail?: string
  invoiceRef?: string
  amount?: number
  currency?: string
  steps: { offsetDays: number; stage?: string; subject?: string; body?: string }[]
}): Promise<number> {
  const db = getSupabaseAdmin()
  const today = new Date()
  const rows = input.steps.map((s) => {
    const due = new Date(today.getTime() + Math.max(0, Number(s.offsetDays) || 0) * 86400_000)
    const dueOn = `${due.getUTCFullYear()}-${String(due.getUTCMonth() + 1).padStart(2, '0')}-${String(due.getUTCDate()).padStart(2, '0')}`
    return {
      user_id: input.userId,
      client: input.client,
      contact_email: input.contactEmail ?? null,
      invoice_ref: input.invoiceRef ?? null,
      amount: typeof input.amount === 'number' ? input.amount : null,
      currency: input.currency || 'EUR',
      stage: STAGES.includes(s.stage as ReminderStage) ? s.stage : 'amiable',
      due_on: dueOn,
      subject: s.subject ?? null,
      body: s.body ?? null,
      status: 'scheduled',
    }
  })
  const { error } = await db.from('payment_reminders').insert(rows)
  if (error) {
    if (isMissingTable(error)) throw new Error('REMINDERS_TABLE_MISSING')
    throw new Error(`Programmation des relances : ${error.message}`)
  }
  return rows.length
}

export async function listReminders(userId: string): Promise<ReminderRow[]> {
  const db = getSupabaseAdmin()
  const { data, error } = await db
    .from('payment_reminders')
    .select('*')
    .eq('user_id', userId)
    .order('due_on', { ascending: true })
    .limit(200)
  if (error) {
    if (isMissingTable(error)) throw new Error('REMINDERS_TABLE_MISSING')
    return []
  }
  return (data as ReminderRow[]) || []
}

export async function getReminder(userId: string, id: string): Promise<ReminderRow | null> {
  const db = getSupabaseAdmin()
  const { data } = await db.from('payment_reminders').select('*').eq('user_id', userId).eq('id', id).maybeSingle()
  return (data as ReminderRow) || null
}

export async function setReminderStatus(userId: string, id: string, status: ReminderStatus): Promise<void> {
  const db = getSupabaseAdmin()
  const patch: Record<string, unknown> = { status }
  if (status === 'sent') patch.sent_at = new Date().toISOString()
  await db.from('payment_reminders').update(patch).eq('user_id', userId).eq('id', id)
}

export async function deleteReminder(userId: string, id: string): Promise<void> {
  const db = getSupabaseAdmin()
  await db.from('payment_reminders').delete().eq('user_id', userId).eq('id', id)
}
