import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { listActions, getAction, markAction } from '@/lib/actions/store'
import { writeToPlatform } from '@/lib/tools/platform-call'
import { getUserEmailConfig } from '@/lib/tools/email-tools'
import { sendEmail } from '@/lib/email'

/**
 * Actions proposées par les agents, en attente de validation.
 *
 * GET  → liste les actions du client (les « pending » d'abord).
 * POST { id, decision: 'approve' | 'reject' }
 *      - 'approve' : SEUL endroit où une écriture est réellement exécutée,
 *        après validation explicite de l'utilisateur connecté.
 *      - 'reject'  : marque l'action comme refusée, rien n'est envoyé.
 */
export async function GET(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  try {
    const actions = await listActions(user.id)
    return NextResponse.json({ actions, needsSetup: false })
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e)
    // La table manque → on le dit explicitement au lieu d'afficher « aucune action ».
    if (msg.includes('ACTIONS_TABLE_MISSING')) {
      return NextResponse.json({ actions: [], needsSetup: true })
    }
    return NextResponse.json({ actions: [], needsSetup: false })
  }
}

export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  let body: any = {}
  try { body = await req.json() } catch { return NextResponse.json({ error: 'Requête invalide.' }, { status: 400 }) }

  const id = typeof body.id === 'string' ? body.id : ''
  const decision = body.decision === 'approve' ? 'approve' : body.decision === 'reject' ? 'reject' : ''
  if (!id || !decision) {
    return NextResponse.json({ error: 'id et decision (approve|reject) requis.' }, { status: 400 })
  }

  // On relit l'action depuis la base, scopée à l'utilisateur : le client ne peut
  // pas exécuter l'action d'un autre compte, ni en modifier le contenu.
  const action = await getAction(user.id, id)
  if (!action) return NextResponse.json({ error: 'Action introuvable.' }, { status: 404 })
  if (action.status !== 'pending') {
    return NextResponse.json({ error: `Action déjà traitée (${action.status}).` }, { status: 409 })
  }

  if (decision === 'reject') {
    await markAction(id, 'rejected')
    return NextResponse.json({ success: true, status: 'rejected' })
  }

  // Exécution réelle, uniquement ici.
  // Cas email : envoi SMTP depuis la boîte du client.
  if (action.provider === 'email') {
    const cfg = await getUserEmailConfig(user.id)
    if (!cfg) {
      await markAction(id, 'failed', 'Aucune boîte email connectée.')
      return NextResponse.json({ success: false, status: 'failed', error: 'Aucune boîte email connectée.' }, { status: 400 })
    }
    const b = (action.body || {}) as { to?: string; subject?: string; text?: string }
    const sent = await sendEmail(cfg, { to: String(b.to || ''), subject: String(b.subject || ''), text: String(b.text || '') })
    if (sent.ok) {
      await markAction(id, 'executed', `Email envoyé (${sent.id || 'ok'}).`)
      return NextResponse.json({ success: true, status: 'executed' })
    }
    await markAction(id, 'failed', sent.error?.slice(0, 2000) || 'Échec')
    return NextResponse.json({ success: false, status: 'failed', error: sent.error }, { status: 502 })
  }

  const res = await writeToPlatform(user.id, action.provider, action.method, action.path, action.body)
  if (res.ok) {
    await markAction(id, 'executed', res.data?.slice(0, 2000) || 'OK')
    return NextResponse.json({ success: true, status: 'executed', result: res.data?.slice(0, 2000) })
  }
  await markAction(id, 'failed', res.error?.slice(0, 2000) || 'Échec')
  return NextResponse.json({ success: false, status: 'failed', error: res.error }, { status: 502 })
}
