// Exécution RÉELLE d'une action (email, SMS, agenda, plateforme). Utilisé par les
// automatisations autonomes (le client a validé l'automatisation → les actions s'exécutent
// sans repasser par « Actions à valider »). Même logique que la route d'approbation manuelle.

import { getUserEmailConfig } from '@/lib/tools/email-tools'
import { sendEmail } from '@/lib/email'
import { sendSms } from '@/lib/sms'
import { bookOnConnectedCalendar } from '@/lib/calendar/providers'
import { buildIcs, type RdvInput } from '@/lib/tools/calendar-tools'
import { writeToPlatform } from '@/lib/tools/platform-call'

export interface ActionInput {
  provider: string
  method: string
  path: string
  body?: unknown
}

export async function executeAction(userId: string, action: ActionInput): Promise<{ ok: boolean; result?: string; error?: string }> {
  if (action.provider === 'email') {
    const cfg = await getUserEmailConfig(userId)
    if (!cfg) return { ok: false, error: 'Aucune boîte email connectée.' }
    const b = (action.body || {}) as { to?: string; subject?: string; text?: string }
    const sent = await sendEmail(cfg, { to: String(b.to || ''), subject: String(b.subject || ''), text: String(b.text || '') })
    return sent.ok ? { ok: true, result: `Email envoyé (${sent.id || 'ok'}).` } : { ok: false, error: sent.error }
  }

  if (action.provider === 'sms') {
    const b = (action.body || {}) as { to?: string; text?: string }
    const sent = await sendSms(String(b.to || ''), String(b.text || ''))
    return sent.ok ? { ok: true, result: `SMS envoyé (${sent.sid || 'ok'}).` } : { ok: false, error: sent.error }
  }

  if (action.provider === 'calendar') {
    const rdv = (action.body || {}) as RdvInput
    const direct = await bookOnConnectedCalendar(userId, rdv)
    if (direct.booked) return { ok: true, result: `RDV créé dans ${direct.provider}.${direct.link ? ' ' + direct.link : ''}` }
    const ics = buildIcs(rdv)
    return ics.ok ? { ok: true, result: 'Événement .ics généré (aucun agenda connecté).' } : { ok: false, error: ics.error || direct.error }
  }

  const res = await writeToPlatform(userId, action.provider, action.method, action.path, action.body)
  return res.ok ? { ok: true, result: res.data?.slice(0, 500) || 'OK' } : { ok: false, error: res.error }
}
