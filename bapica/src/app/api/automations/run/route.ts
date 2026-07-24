import { NextRequest, NextResponse } from 'next/server'
import Anthropic from '@anthropic-ai/sdk'
import { getAutomationById, setLastRun } from '@/lib/automations/store'
import { runAgentConsult } from '@/lib/tools/agent-consult'
import { buildBusinessBrief } from '@/lib/business-context'
import { buildDeliverable } from '@/lib/deliverables'
import { createDeliverable } from '@/lib/deliverables/store'
import { getSupabaseAdmin } from '@/lib/supabase-admin'

/**
 * POST /api/automations/run — déclenché par N8N (workflow planifié).
 * Body : { automationId, secret }. Le secret par-automatisation fait office d'auth.
 *
 * Exécute l'agent responsable sur la consigne de l'automatisation, avec le contexte du
 * client, et range le résultat dans « Documents ». Les actions EXTERNES éventuelles passent
 * par les outils habituels (« Actions à valider ») — l'accord du client reste respecté.
 */
export async function POST(req: NextRequest) {
  let body: any = {}
  try { body = await req.json() } catch { return NextResponse.json({ error: 'Requête invalide.' }, { status: 400 }) }
  const id = String(body.automationId || '')
  const secret = String(body.secret || '')
  if (!id || !secret) return NextResponse.json({ error: 'automationId et secret requis.' }, { status: 400 })

  const a = await getAutomationById(id)
  if (!a || a.run_secret !== secret) return NextResponse.json({ error: 'Non autorisé.' }, { status: 401 })
  if (a.status !== 'active') return NextResponse.json({ skipped: true, reason: `statut ${a.status}` })

  const apiKey = process.env.ANTHROPIC_API_KEY
  if (!apiKey) return NextResponse.json({ error: 'ANTHROPIC_API_KEY manquante.' }, { status: 503 })

  // Contexte du client (brief business depuis les métadonnées, via service_role).
  let context = ''
  try {
    const admin = getSupabaseAdmin()
    const { data } = await admin.auth.admin.getUserById(a.user_id)
    const onboarding = (data?.user?.user_metadata as any)?.onboarding_data || {}
    context = buildBusinessBrief(onboarding)
  } catch { /* contexte best-effort */ }

  try {
    const client = new Anthropic({ apiKey })
    const output = await runAgentConsult(client, a.agent_id || 'general', a.description, context)

    // Range le résultat comme document daté pour que le client le retrouve.
    const dateStr = new Date().toLocaleDateString('fr')
    const file = buildDeliverable({ kind: 'markdown', title: `${a.title} — ${dateStr}`, content: `# ${a.title}\n\n${output}` })
    await createDeliverable({
      userId: a.user_id, agentId: a.agent_id || 'general',
      kind: 'markdown', title: `${a.title} — ${dateStr}`,
      filename: file.filename, mime: file.mime, content: file.content,
    }).catch(() => {})

    await setLastRun(id)
    return NextResponse.json({ ok: true, ran: a.title })
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e instanceof Error ? e.message : e) }, { status: 500 })
  }
}
