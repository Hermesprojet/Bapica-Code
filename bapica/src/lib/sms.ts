// Envoi de SMS via Twilio — pour les comptes rendus d'appel (Hugo/Nadia) et toute
// notification courte. Réutilise les identifiants Twilio déjà présents (SID + auth token) ;
// nécessite en plus un numéro expéditeur SMS : TWILIO_SMS_NUMBER (ex : +14155551234) —
// ou, à défaut, un Messaging Service SID (TWILIO_MESSAGING_SERVICE_SID).

export function smsConfigured(): boolean {
  return !!(
    process.env.TWILIO_ACCOUNT_SID &&
    process.env.TWILIO_AUTH_TOKEN &&
    (process.env.TWILIO_SMS_NUMBER || process.env.TWILIO_MESSAGING_SERVICE_SID)
  )
}

/** Envoie un SMS. Renvoie le détail de l'erreur Twilio pour le diagnostic. */
export async function sendSms(to: string, body: string): Promise<{ ok: boolean; status?: number; error?: string; sid?: string }> {
  const sid = process.env.TWILIO_ACCOUNT_SID
  const auth = process.env.TWILIO_AUTH_TOKEN
  const from = process.env.TWILIO_SMS_NUMBER
  const messagingService = process.env.TWILIO_MESSAGING_SERVICE_SID
  if (!sid || !auth || (!from && !messagingService)) {
    const missing = [
      !sid && 'TWILIO_ACCOUNT_SID',
      !auth && 'TWILIO_AUTH_TOKEN',
      !from && !messagingService && 'TWILIO_SMS_NUMBER (ou TWILIO_MESSAGING_SERVICE_SID)',
    ].filter(Boolean).join(', ')
    return { ok: false, error: `Variables manquantes côté serveur : ${missing}` }
  }

  const dest = String(to || '').trim()
  if (!dest) return { ok: false, error: 'Numéro destinataire manquant.' }

  const params: Record<string, string> = { To: dest, Body: String(body || '').slice(0, 1600) }
  if (messagingService) params.MessagingServiceSid = messagingService
  else params.From = String(from)

  try {
    const res = await fetch(`https://api.twilio.com/2010-04-01/Accounts/${sid}/Messages.json`, {
      method: 'POST',
      headers: {
        Authorization: 'Basic ' + Buffer.from(`${sid}:${auth}`).toString('base64'),
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams(params).toString(),
      signal: AbortSignal.timeout(15000),
    })
    const raw = await res.text().catch(() => '')
    if (res.ok) {
      let sms_sid = ''
      try { sms_sid = JSON.parse(raw).sid || '' } catch { /* ignore */ }
      return { ok: true, status: res.status, sid: sms_sid }
    }
    let detail = raw.slice(0, 400)
    try { const j = JSON.parse(raw); detail = `${j.code ?? ''} ${j.message ?? ''}`.trim() || detail } catch { /* brut */ }
    return { ok: false, status: res.status, error: detail }
  } catch (e) {
    return { ok: false, error: String(e instanceof Error ? e.message : e) }
  }
}
