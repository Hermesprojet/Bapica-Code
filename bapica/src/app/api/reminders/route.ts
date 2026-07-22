import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { listReminders, getReminder, setReminderStatus, deleteReminder, type ReminderStatus } from '@/lib/reminders/store'
import { createAction } from '@/lib/actions/store'

/**
 * GET    /api/reminders                       → liste les relances programmées.
 * POST   /api/reminders { id, action }        → 'sent' | 'cancelled' | 'paid' | 'prepare_email'
 *          'prepare_email' crée une action email « à valider » à partir de la relance.
 * DELETE /api/reminders { id }                → supprime une relance.
 */
export async function GET(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  try {
    const reminders = await listReminders(user.id)
    return NextResponse.json({ reminders, needsSetup: false })
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e)
    if (msg.includes('REMINDERS_TABLE_MISSING')) return NextResponse.json({ reminders: [], needsSetup: true })
    return NextResponse.json({ reminders: [], needsSetup: false })
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

  const reminder = await getReminder(user.id, id)
  if (!reminder) return NextResponse.json({ error: 'Relance introuvable.' }, { status: 404 })

  if (action === 'prepare_email') {
    if (!reminder.contact_email) {
      return NextResponse.json({ error: 'Aucun email de contact sur cette relance.' }, { status: 400 })
    }
    try {
      const actionId = await createAction({
        userId: user.id,
        agentId: 'accounting',
        provider: 'email',
        method: 'SEND',
        path: '',
        body: {
          to: reminder.contact_email,
          subject: reminder.subject || `Relance — facture ${reminder.invoice_ref || ''}`.trim(),
          text: reminder.body || '',
        },
        summary: `Relance ${reminder.stage} — ${reminder.client}${reminder.invoice_ref ? ` (facture ${reminder.invoice_ref})` : ''}`,
      })
      await setReminderStatus(user.id, id, 'sent')
      return NextResponse.json({ success: true, action_id: actionId, status: 'sent' })
    } catch (err) {
      const m = String(err instanceof Error ? err.message : err)
      return NextResponse.json({ error: m.includes('ACTIONS_TABLE_MISSING') ? 'Base non initialisée : exécutez supabase-schema.sql.' : m }, { status: 500 })
    }
  }

  if (['sent', 'cancelled', 'paid'].includes(action)) {
    await setReminderStatus(user.id, id, action as ReminderStatus)
    return NextResponse.json({ success: true, status: action })
  }

  return NextResponse.json({ error: 'Action inconnue.' }, { status: 400 })
}

export async function DELETE(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  let body: any = {}
  try { body = await req.json() } catch { /* ignore */ }
  const id = typeof body.id === 'string' ? body.id : ''
  if (!id) return NextResponse.json({ error: 'id requis.' }, { status: 400 })
  await deleteReminder(user.id, id)
  return NextResponse.json({ success: true })
}
