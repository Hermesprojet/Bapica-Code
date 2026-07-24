import { getSupabaseAdmin } from '@/lib/supabase-admin'
import { randomBytes } from 'crypto'

// Automatisations récurrentes (table automations) — accès service_role uniquement.
// L'agent propose (status pending) ; le client valide (active) ; N8N déclenche /run.

export type AutomationStatus = 'pending' | 'active' | 'paused'

export interface AutomationRow {
  id: string
  user_id: string
  agent_id: string | null
  title: string
  description: string
  cron: string
  schedule_label: string | null
  status: string
  n8n_workflow_id: string | null
  run_secret: string
  last_run_at: string | null
  created_at: string
}

function isMissingTable(error: { code?: string; message?: string } | null): boolean {
  return error?.code === '42P01' || /automations.*does not exist/i.test(error?.message || '')
}

export async function createAutomation(input: {
  userId: string
  agentId?: string
  title: string
  description: string
  cron: string
  scheduleLabel?: string
}): Promise<string> {
  const db = getSupabaseAdmin()
  const { data, error } = await db
    .from('automations')
    .insert({
      user_id: input.userId,
      agent_id: input.agentId ?? null,
      title: input.title,
      description: input.description,
      cron: input.cron,
      schedule_label: input.scheduleLabel ?? null,
      status: 'pending',
      run_secret: randomBytes(24).toString('hex'),
    })
    .select('id')
    .single()
  if (error) {
    if (isMissingTable(error)) throw new Error('AUTOMATIONS_TABLE_MISSING')
    throw new Error(`Création de l'automatisation : ${error.message}`)
  }
  return (data as { id: string }).id
}

export async function listAutomations(userId: string): Promise<AutomationRow[]> {
  const db = getSupabaseAdmin()
  const { data, error } = await db.from('automations').select('*').eq('user_id', userId).order('created_at', { ascending: false }).limit(100)
  if (error) {
    if (isMissingTable(error)) throw new Error('AUTOMATIONS_TABLE_MISSING')
    return []
  }
  return (data as AutomationRow[]) || []
}

export async function getAutomation(userId: string, id: string): Promise<AutomationRow | null> {
  const db = getSupabaseAdmin()
  const { data } = await db.from('automations').select('*').eq('user_id', userId).eq('id', id).maybeSingle()
  return (data as AutomationRow) || null
}

/** Pour la route /run (appelée par N8N) : lecture par id seul, le secret fait foi. */
export async function getAutomationById(id: string): Promise<AutomationRow | null> {
  const db = getSupabaseAdmin()
  const { data } = await db.from('automations').select('*').eq('id', id).maybeSingle()
  return (data as AutomationRow) || null
}

export async function setStatus(userId: string, id: string, status: AutomationStatus): Promise<void> {
  const db = getSupabaseAdmin()
  await db.from('automations').update({ status }).eq('user_id', userId).eq('id', id)
}

export async function setWorkflow(userId: string, id: string, workflowId: string | null): Promise<void> {
  const db = getSupabaseAdmin()
  await db.from('automations').update({ n8n_workflow_id: workflowId }).eq('user_id', userId).eq('id', id)
}

export async function setLastRun(id: string): Promise<void> {
  const db = getSupabaseAdmin()
  await db.from('automations').update({ last_run_at: new Date().toISOString() }).eq('id', id)
}

export async function deleteAutomation(userId: string, id: string): Promise<void> {
  const db = getSupabaseAdmin()
  await db.from('automations').delete().eq('user_id', userId).eq('id', id)
}
