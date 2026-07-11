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
export type IntegrationProvider = 
  // Communication
  'gmail' | 'outlook' | 'office365' | 'slack' | 'teams' | 'discord' | 'whatsapp' | 'telegram' |
  // Comptabilité & Finance
  'pennylane' | 'quickbooks' | 'xero' | 'sage' | 'cegid' | 'zoho_books' | 'wave' | 'stripe' | 'paypal' | 'square' | 'mollie' | 'adyen' | 'qonto' | 'revolut' | 'wise' |
  // CRM
  'twenty' | 'hubspot' | 'salesforce' | 'pipedrive' | 'zoho_crm' | 'monday_crm' |
  // Email Marketing
  'brevo' | 'mailchimp' | 'mailjet' | 'sendgrid' | 'resend' |
  // E-commerce
  'shopify' | 'woocommerce' | 'prestashop' | 'magento' | 'wix' |
  // Calendrier
  'google_calendar' | 'calendly' | 'outlook_calendar' |
  // Gestion de projet
  'trello' | 'asana' | 'monday' | 'jira' | 'clickup' | 'notion' |
  // Cloud Storage
  'google_drive' | 'dropbox' | 'onedrive' | 'box' |
  // Dev
  'github' | 'gitlab' | 'bitbucket' | 'vercel' | 'netlify' |
  // Design
  'figma' | 'canva' | 'adobe' |
  // Automatisation
  'zapier' | 'make' | 'n8n' | 'ifttt' |
  // RH & Paie
  'payfit' | 'lucca' | 'adp' | 'bamboohr' |
  // Analytics
  'google_analytics' | 'matomo' | 'hotjar' | 'mixpanel' |
  // Social Media
  'linkedin' | 'twitter' | 'instagram' | 'facebook' | 'tiktok' |
  // Documents & Signature
  'google_docs' | 'docusign' | 'hellosign' | 'pandadoc' |
  // Support Client
  'zendesk' | 'intercom' | 'freshdesk' | 'crisp' |
  // Téléphonie VoIP
  'aircall' | 'ringcentral' | 'twilio' | 'vapi' |
  // Juridique
  'legalstart' | 'captain_contrat' | 'leeway'

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
export function getAvailableIntegrations(): { id: IntegrationProvider; name: string; description: string; icon: string; category: string }[] {
  return [
    // 📧 Communication
    { id: 'gmail', name: 'Gmail', description: 'Emails Google', icon: '📧', category: 'Communication' },
    { id: 'outlook', name: 'Outlook', description: 'Emails Microsoft', icon: '📨', category: 'Communication' },
    { id: 'office365', name: 'Office 365', description: 'Suite Microsoft complète', icon: '📦', category: 'Communication' },
    { id: 'slack', name: 'Slack', description: 'Messagerie équipe', icon: '💬', category: 'Communication' },
    { id: 'teams', name: 'Microsoft Teams', description: 'Visio et collaboration', icon: '📹', category: 'Communication' },
    { id: 'discord', name: 'Discord', description: 'Communauté et vocal', icon: '🎮', category: 'Communication' },
    { id: 'whatsapp', name: 'WhatsApp Business', description: 'Messages clients', icon: '💚', category: 'Communication' },
    { id: 'telegram', name: 'Telegram', description: 'Messagerie instantanée', icon: '✈️', category: 'Communication' },
    // 📊 Compta & Finance
    { id: 'pennylane', name: 'Pennylane', description: 'Compta & facturation FR', icon: '📊', category: 'Finance' },
    { id: 'quickbooks', name: 'QuickBooks', description: 'Compta internationale', icon: '📒', category: 'Finance' },
    { id: 'xero', name: 'Xero', description: 'Compta cloud', icon: '📕', category: 'Finance' },
    { id: 'sage', name: 'Sage', description: 'Compta & paie', icon: '📗', category: 'Finance' },
    { id: 'cegid', name: 'Cegid', description: 'ERP & compta FR', icon: '📘', category: 'Finance' },
    { id: 'zoho_books', name: 'Zoho Books', description: 'Compta en ligne', icon: '📙', category: 'Finance' },
    { id: 'stripe', name: 'Stripe', description: 'Paiements en ligne', icon: '💳', category: 'Finance' },
    { id: 'paypal', name: 'PayPal', description: 'Paiements internationaux', icon: '💰', category: 'Finance' },
    { id: 'square', name: 'Square', description: 'Paiement physique & web', icon: '🏪', category: 'Finance' },
    { id: 'mollie', name: 'Mollie', description: 'Paiements EU', icon: '💶', category: 'Finance' },
    { id: 'qonto', name: 'Qonto', description: 'Banque pro en ligne', icon: '🏦', category: 'Finance' },
    { id: 'revolut', name: 'Revolut Business', description: 'Banque internationale', icon: '🌍', category: 'Finance' },
    // 👥 CRM
    { id: 'twenty', name: 'Twenty CRM', description: 'CRM open-source', icon: '👥', category: 'CRM' },
    { id: 'hubspot', name: 'HubSpot', description: 'CRM & marketing', icon: '🎯', category: 'CRM' },
    { id: 'salesforce', name: 'Salesforce', description: 'CRM enterprise', icon: '☁️', category: 'CRM' },
    { id: 'pipedrive', name: 'Pipedrive', description: 'Pipeline commercial', icon: '📈', category: 'CRM' },
    { id: 'zoho_crm', name: 'Zoho CRM', description: 'CRM tout-en-un', icon: '🔵', category: 'CRM' },
    // 📬 Email Marketing
    { id: 'brevo', name: 'Brevo', description: 'Email & SMS marketing', icon: '📬', category: 'Marketing' },
    { id: 'mailchimp', name: 'Mailchimp', description: 'Newsletters', icon: '🐵', category: 'Marketing' },
    { id: 'mailjet', name: 'Mailjet', description: 'Emails transactionnels', icon: '✉️', category: 'Marketing' },
    { id: 'sendgrid', name: 'SendGrid', description: 'API email', icon: '📤', category: 'Marketing' },
    // 🛒 E-commerce
    { id: 'shopify', name: 'Shopify', description: 'Boutique en ligne', icon: '🛍️', category: 'E-commerce' },
    { id: 'woocommerce', name: 'WooCommerce', description: 'E-commerce WordPress', icon: '🔌', category: 'E-commerce' },
    { id: 'prestashop', name: 'PrestaShop', description: 'E-commerce FR', icon: '🇫🇷', category: 'E-commerce' },
    // 📅 Calendrier
    { id: 'google_calendar', name: 'Google Calendar', description: 'Agenda Google', icon: '📅', category: 'Organisation' },
    { id: 'calendly', name: 'Calendly', description: 'Prise de RDV auto', icon: '🔗', category: 'Organisation' },
    { id: 'outlook_calendar', name: 'Outlook Calendar', description: 'Agenda Microsoft', icon: '📆', category: 'Organisation' },
    // 📋 Gestion de projet
    { id: 'trello', name: 'Trello', description: 'Kanban visuel', icon: '📋', category: 'Organisation' },
    { id: 'asana', name: 'Asana', description: 'Gestion de projet', icon: '✅', category: 'Organisation' },
    { id: 'monday', name: 'Monday.com', description: 'Work OS', icon: '🔷', category: 'Organisation' },
    { id: 'jira', name: 'Jira', description: 'Dev & agile', icon: '🐛', category: 'Organisation' },
    { id: 'clickup', name: 'ClickUp', description: 'Productivité tout-en-un', icon: '⚡', category: 'Organisation' },
    { id: 'notion', name: 'Notion', description: 'Docs & wiki', icon: '📝', category: 'Organisation' },
    // ☁️ Cloud Storage
    { id: 'google_drive', name: 'Google Drive', description: 'Stockage Google', icon: '📁', category: 'Cloud' },
    { id: 'dropbox', name: 'Dropbox', description: 'Stockage cloud', icon: '📦', category: 'Cloud' },
    { id: 'onedrive', name: 'OneDrive', description: 'Stockage Microsoft', icon: '☁️', category: 'Cloud' },
    // 💻 Dev
    { id: 'github', name: 'GitHub', description: 'Code & CI/CD', icon: '🐙', category: 'Dev' },
    { id: 'gitlab', name: 'GitLab', description: 'DevOps', icon: '🦊', category: 'Dev' },
    { id: 'vercel', name: 'Vercel', description: 'Déploiement web', icon: '▲', category: 'Dev' },
    // 🎨 Design
    { id: 'figma', name: 'Figma', description: 'Design collaboratif', icon: '🎨', category: 'Design' },
    { id: 'canva', name: 'Canva', description: 'Design facile', icon: '🖼️', category: 'Design' },
    { id: 'adobe', name: 'Adobe CC', description: 'Suite créative', icon: '🌈', category: 'Design' },
    // ⚡ Automatisation
    { id: 'zapier', name: 'Zapier', description: 'Automatisation no-code', icon: '⚡', category: 'Automatisation' },
    { id: 'make', name: 'Make (Integromat)', description: 'Automatisation avancée', icon: '🔧', category: 'Automatisation' },
    { id: 'n8n', name: 'n8n', description: 'Automatisation open-source', icon: '🔗', category: 'Automatisation' },
    // 👔 RH & Paie
    { id: 'payfit', name: 'PayFit', description: 'Paie & RH', icon: '💼', category: 'RH' },
    { id: 'lucca', name: 'Lucca', description: 'Congés & notes de frais', icon: '🏖️', category: 'RH' },
    { id: 'bamboohr', name: 'BambooHR', description: 'SIRH PME', icon: '🎋', category: 'RH' },
    // 📈 Analytics
    { id: 'google_analytics', name: 'Google Analytics', description: 'Trafic & audiences', icon: '📈', category: 'Analytics' },
    { id: 'matomo', name: 'Matomo', description: 'Analytics RGPD', icon: '🔒', category: 'Analytics' },
    { id: 'hotjar', name: 'Hotjar', description: 'Heatmaps & sessions', icon: '🔥', category: 'Analytics' },
    { id: 'mixpanel', name: 'Mixpanel', description: 'Product analytics', icon: '📊', category: 'Analytics' },
    // 📱 Social Media
    { id: 'linkedin', name: 'LinkedIn', description: 'Prospection B2B', icon: '🔗', category: 'Social' },
    { id: 'twitter', name: 'Twitter / X', description: 'Veille & actualité', icon: '🐦', category: 'Social' },
    { id: 'instagram', name: 'Instagram', description: 'Visuel & marque', icon: '📸', category: 'Social' },
    { id: 'facebook', name: 'Facebook', description: 'Audience large', icon: '👤', category: 'Social' },
    { id: 'tiktok', name: 'TikTok', description: 'Vidéo courte', icon: '🎵', category: 'Social' },
    // 📄 Documents & Signature
    { id: 'google_docs', name: 'Google Docs', description: 'Documents collaboratifs', icon: '📄', category: 'Documents' },
    { id: 'docusign', name: 'DocuSign', description: 'Signature électronique', icon: '✍️', category: 'Documents' },
    { id: 'pandadoc', name: 'PandaDoc', description: 'Devis & contrats', icon: '🐼', category: 'Documents' },
    // 🎧 Support
    { id: 'zendesk', name: 'Zendesk', description: 'Support client', icon: '🎧', category: 'Support' },
    { id: 'intercom', name: 'Intercom', description: 'Chat & support', icon: '💬', category: 'Support' },
    { id: 'freshdesk', name: 'Freshdesk', description: 'Helpdesk', icon: '🍃', category: 'Support' },
    { id: 'crisp', name: 'Crisp', description: 'Chat & CRM', icon: '💙', category: 'Support' },
    // 📞 Téléphonie
    { id: 'aircall', name: 'Aircall', description: 'Téléphonie pro', icon: '📞', category: 'Téléphonie' },
    { id: 'ringcentral', name: 'RingCentral', description: 'VoIP entreprise', icon: '🔔', category: 'Téléphonie' },
    { id: 'twilio', name: 'Twilio', description: 'API communications', icon: '📡', category: 'Téléphonie' },
    { id: 'vapi', name: 'Vapi', description: 'Agents vocaux IA', icon: '🤖', category: 'Téléphonie' },
    // ⚖️ Juridique
    { id: 'legalstart', name: 'Legalstart', description: 'Documents juridiques', icon: '⚖️', category: 'Juridique' },
    { id: 'captain_contrat', name: 'Captain Contrat', description: 'Contrats pros', icon: '📜', category: 'Juridique' },
  ]
}
