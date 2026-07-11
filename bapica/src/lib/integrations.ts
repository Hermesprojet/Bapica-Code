/**
 * Bapica Integrations Hub
 * 
 * Connecte les agents aux plateformes externes pour exécuter des actions réelles.
 * 
 * Intégrations supportées:
 * - Gmail/Google Workspace: envoyer des emails, lire boîte
 * - Pennylane: compta, facturation, trésorerie
 * - Stripe: paiements, abonnements (déjà fait)
 * - Twenty CRM: contacts, opportunités (déjà fait)
 * - Calendly/Google Calendar: rendez-vous
 * - Notion: documentation, wiki
 * - Slack: notifications, messages
 */

// Types génériques
export type IntegrationProvider = 'gmail' | 'pennylane' | 'stripe' | 'twenty' | 'google_calendar' | 'notion' | 'slack'

export interface IntegrationCredentials {
  provider: IntegrationProvider
  accessToken: string
  refreshToken?: string
  expiresAt?: number
  metadata?: Record<string, string>
}

export interface IntegrationAction {
  provider: IntegrationProvider
  action: string
  params: Record<string, any>
}

// ─── GMAIL ────────────────────────────────────────────────

export async function gmailSend(params: {
  to: string
  subject: string
  body: string
  cc?: string
  bcc?: string
  accessToken: string
}): Promise<{ success: boolean; messageId?: string; error?: string }> {
  try {
    // Construire l'email au format MIME
    const email = [
      `From: me`,
      `To: ${params.to}`,
      params.cc ? `Cc: ${params.cc}` : '',
      params.bcc ? `Bcc: ${params.bcc}` : '',
      `Subject: =?UTF-8?B?${Buffer.from(params.subject).toString('base64')}?=`,
      'Content-Type: text/html; charset=UTF-8',
      '',
      params.body,
    ].filter(Boolean).join('\r\n')

    const base64 = Buffer.from(email).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')

    const res = await fetch('https://gmail.googleapis.com/gmail/v1/users/me/messages/send', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${params.accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ raw: base64 }),
    })

    if (!res.ok) {
      const err = await res.json()
      return { success: false, error: (err as any).error?.message || 'Gmail API error' }
    }

    const data = await res.json()
    return { success: true, messageId: (data as any).id }
  } catch (e) {
    return { success: false, error: String(e) }
  }
}

export async function gmailReadRecent(accessToken: string, maxResults = 5): Promise<any[]> {
  try {
    const res = await fetch(
      `https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=${maxResults}&q=is:unread`,
      { headers: { Authorization: `Bearer ${accessToken}` } }
    )
    if (!res.ok) return []
    const data = await res.json()
    return (data as any).messages || []
  } catch {
    return []
  }
}

// ─── PENNYLANE ────────────────────────────────────────────

export async function pennylaneGetInvoices(apiKey: string, status?: string): Promise<any[]> {
  try {
    const params = status ? `?filter[status]=${status}` : ''
    const res = await fetch(`https://app.pennylane.com/api/external/v1/customer_invoices${params}`, {
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
    })
    if (!res.ok) return []
    const data = await res.json()
    return (data as any).customer_invoices || []
  } catch {
    return []
  }
}

export async function pennylaneCreateInvoice(apiKey: string, invoice: {
  customer_id: string
  date: string
  deadline: string
  items: { label: string; quantity: number; unit_price: number }[]
}): Promise<{ success: boolean; id?: string }> {
  try {
    const res = await fetch('https://app.pennylane.com/api/external/v1/customer_invoices', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ customer_invoice: invoice }),
    })
    if (!res.ok) return { success: false }
    const data = await res.json()
    return { success: true, id: (data as any).customer_invoice?.id }
  } catch {
    return { success: false }
  }
}

export async function pennylaneGetCashflow(apiKey: string): Promise<any> {
  try {
    const res = await fetch('https://app.pennylane.com/api/external/v1/cash_flow', {
      headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
    })
    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}

// ─── GOOGLE CALENDAR ──────────────────────────────────────

export async function calendarCreateEvent(params: {
  summary: string
  description?: string
  startTime: string
  endTime: string
  attendees?: string[]
  accessToken: string
}): Promise<{ success: boolean; eventId?: string }> {
  try {
    const res = await fetch('https://www.googleapis.com/calendar/v3/calendars/primary/events', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${params.accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        summary: params.summary,
        description: params.description || '',
        start: { dateTime: params.startTime, timeZone: 'Europe/Paris' },
        end: { dateTime: params.endTime, timeZone: 'Europe/Paris' },
        attendees: (params.attendees || []).map(email => ({ email })),
      }),
    })
    if (!res.ok) return { success: false }
    const data = await res.json()
    return { success: true, eventId: (data as any).id }
  } catch {
    return { success: false }
  }
}

// ─── SLACK ─────────────────────────────────────────────────

export async function slackSendMessage(params: {
  channel: string
  text: string
  webhookUrl: string
}): Promise<boolean> {
  try {
    const res = await fetch(params.webhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ channel: params.channel, text: params.text }),
    })
    return res.ok
  } catch {
    return false
  }
}

// ─── NOTION ────────────────────────────────────────────────

export async function notionCreatePage(params: {
  parentId: string
  title: string
  content: string
  accessToken: string
}): Promise<{ success: boolean }> {
  try {
    const res = await fetch('https://api.notion.com/v1/pages', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${params.accessToken}`,
        'Content-Type': 'application/json',
        'Notion-Version': '2022-06-28',
      },
      body: JSON.stringify({
        parent: { page_id: params.parentId },
        properties: {
          title: { title: [{ text: { content: params.title } }] },
        },
        children: [
          {
            object: 'block',
            type: 'paragraph',
            paragraph: { rich_text: [{ text: { content: params.content } }] },
          },
        ],
      }),
    })
    return { success: res.ok }
  } catch {
    return { success: false }
  }
}

// ─── HUB DISPATCHER ────────────────────────────────────────

/**
 * Dispatcher: reçoit une action et l'exécute sur la bonne plateforme
 */
export async function dispatchAction(
  action: IntegrationAction,
  credentials: Record<string, string>
): Promise<any> {
  try {
    switch (action.provider) {
      case 'gmail':
        if (action.action === 'send') {
          const p = action.params as { to: string; subject: string; body: string; cc?: string; bcc?: string }
          return gmailSend({ to: p.to, subject: p.subject, body: p.body, cc: p.cc, bcc: p.bcc, accessToken: credentials.gmail_token })
        }
        break
      case 'pennylane':
        if (action.action === 'get_invoices') {
          return pennylaneGetInvoices(credentials.pennylane_key)
        }
        if (action.action === 'create_invoice') {
          const p = action.params as { customer_id: string; date: string; deadline: string; items: { label: string; quantity: number; unit_price: number }[] }
          return pennylaneCreateInvoice(credentials.pennylane_key, p)
        }
        break
      case 'google_calendar':
        if (action.action === 'create_event') {
          const p = action.params as { summary: string; description?: string; startTime: string; endTime: string; attendees?: string[] }
          return calendarCreateEvent({ summary: p.summary, description: p.description, startTime: p.startTime, endTime: p.endTime, attendees: p.attendees, accessToken: credentials.calendar_token })
        }
        break
      case 'slack':
        if (action.action === 'send') {
          const p = action.params as { channel: string; text: string }
          return slackSendMessage({ channel: p.channel, text: p.text, webhookUrl: credentials.slack_webhook })
        }
        break
      case 'notion':
        if (action.action === 'create_page') {
          const p = action.params as { parentId: string; title: string; content: string }
          return notionCreatePage({ parentId: p.parentId, title: p.title, content: p.content, accessToken: credentials.notion_token })
        }
        break
    }
  } catch (e) {
    return { success: false, error: String(e) }
  }
  return { success: false, error: 'Action non supportée' }
}

/**
 * Liste les intégrations disponibles pour un utilisateur
 */
export function getAvailableIntegrations(): { id: IntegrationProvider; name: string; description: string; icon: string }[] {
  return [
    { id: 'gmail', name: 'Gmail', description: 'Envoyer et lire des emails', icon: '📧' },
    { id: 'pennylane', name: 'Pennylane', description: 'Comptabilité et facturation', icon: '📊' },
    { id: 'stripe', name: 'Stripe', description: 'Paiements et abonnements', icon: '💳' },
    { id: 'twenty', name: 'Twenty CRM', description: 'Contacts et pipeline', icon: '👥' },
    { id: 'google_calendar', name: 'Google Calendar', description: 'Rendez-vous et agenda', icon: '📅' },
    { id: 'notion', name: 'Notion', description: 'Documentation et wiki', icon: '📝' },
    { id: 'slack', name: 'Slack', description: 'Notifications et messages', icon: '💬' },
  ]
}
