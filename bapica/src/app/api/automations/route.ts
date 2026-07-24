import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { listAutomations, getAutomation, setStatus, setWorkflow, deleteAutomation } from '@/lib/automations/store'
import { createScheduledWorkflow, setWorkflowActive, deleteWorkflow, n8nConfigured } from '@/lib/n8n'

/**
 * GET  /api/automations                 → liste les automatisations du client.
 * POST /api/automations { id, action }  → 'approve' | 'pause' | 'resume' | 'delete'
 *   'approve' : SEUL endroit qui active — après validation explicite du client (son accord).
 *               Crée le workflow N8N planifié si N8N est configuré.
 */
export async function GET(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  try {
    const automations = await listAutomations(user.id)
    return NextResponse.json({ automations, n8n: n8nConfigured(), needsSetup: false })
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e)
    if (msg.includes('AUTOMATIONS_TABLE_MISSING')) return NextResponse.json({ automations: [], n8n: n8nConfigured(), needsSetup: true })
    return NextResponse.json({ automations: [], n8n: n8nConfigured(), needsSetup: false })
  }
}

export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  let body: any = {}
  try { body = await req.json() } catch { return NextResponse.json({ error: 'Requête invalide.' }, { status: 400 }) }
  const id = typeof body.id === 'string' ? body.id : ''
  const action = String(body.action || '')
  if (!id || !action) return NextResponse.json({ error: 'id et action requis.' }, { status: 400 })

  const a = await getAutomation(user.id, id)
  if (!a) return NextResponse.json({ error: 'Automatisation introuvable.' }, { status: 404 })

  if (action === 'delete') {
    if (a.n8n_workflow_id) await deleteWorkflow(a.n8n_workflow_id).catch(() => {})
    await deleteAutomation(user.id, id)
    return NextResponse.json({ success: true })
  }

  if (action === 'pause') {
    if (a.n8n_workflow_id) await setWorkflowActive(a.n8n_workflow_id, false).catch(() => {})
    await setStatus(user.id, id, 'paused')
    return NextResponse.json({ success: true, status: 'paused' })
  }

  if (action === 'approve' || action === 'resume') {
    let note: string | undefined
    // Crée (ou réactive) le workflow N8N planifié.
    if (n8nConfigured()) {
      if (a.n8n_workflow_id) {
        await setWorkflowActive(a.n8n_workflow_id, true).catch(() => {})
      } else {
        const base = (process.env.NEXT_PUBLIC_APP_URL || '').replace(/\/$/, '')
        const r = await createScheduledWorkflow({
          name: a.title, cron: a.cron, runUrl: `${base}/api/automations/run`,
          automationId: a.id, secret: a.run_secret,
        })
        if (r.ok && r.workflowId) { await setWorkflow(user.id, id, r.workflowId); note = r.error }
        else note = r.error
      }
    } else {
      note = "N8N non configuré : l'automatisation est enregistrée mais ne se déclenchera pas tant que N8N n'est pas branché."
    }
    await setStatus(user.id, id, 'active')
    return NextResponse.json({ success: true, status: 'active', note })
  }

  return NextResponse.json({ error: 'Action inconnue.' }, { status: 400 })
}
