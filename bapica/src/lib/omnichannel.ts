/**
 * Bapica Omnichannel — WhatsApp, Messenger, Telegram
 * 
 * Les agents Bapica sont joignables sur toutes les messageries.
 * Un seul système de routage, toutes les plateformes.
 */

// ─── TYPES COMMUNS ─────────────────────────────────────────

export type MessageChannel = 'whatsapp' | 'messenger' | 'telegram' | 'web'

export interface IncomingMessage {
  channel: MessageChannel
  userId: string
  userName: string
  text: string
  timestamp: string
  metadata: Record<string, string>
}

export interface OutgoingMessage {
  channel: MessageChannel
  userId: string
  text: string
  options?: OutgoingOption[]
}

export interface OutgoingOption {
  id: string
  label: string
}

// ─── ROUTEUR DE MESSAGES ───────────────────────────────────

/**
 * Détecte l'intention et route vers le bon agent Bapica
 */
export function routeMessage(msg: IncomingMessage): {
  agentId: string
  greeting: string
  confidence: number
} {
  const t = msg.text.toLowerCase()

  // Salutations
  if (t.match(/^(bonjour|salut|hello|bjr|hi|hey|yo|coucou)/)) {
    return {
      agentId: 'prospection-strategie',
      greeting: `Bonjour ${msg.userName.split(' ')[0]} ! 👋\n\nJe suis Bapica, votre équipe d'agents IA. Comment puis-je vous aider aujourd'hui ?\n\n📈 Croissance & CA\n📊 Analyse business\n🔌 Connecter vos outils\n🤖 Découvrir les 10 agents\n\nDites-moi simplement ce dont vous avez besoin.`,
      confidence: 0.95,
    }
  }

  // Intention prospection
  if (t.match(/client|prospect|vente|ca|chiffre|croissance|acquérir|développer/)) {
    return { agentId: 'prospection-strategie', greeting: '', confidence: 0.85 }
  }

  // Intention compta
  if (t.match(/compta|facture|trésorerie|tva|fiscal|bilan|déclaration/)) {
    return { agentId: 'accounting', greeting: '', confidence: 0.85 }
  }

  // Intention support
  if (t.match(/problème|bug|erreur|panne|aide|help|urgent|bloqué/)) {
    return { agentId: 'support', greeting: '', confidence: 0.85 }
  }

  // Intention recrutement
  if (t.match(/recruter|embauche|cv|candidat|poste|offre|entretien/)) {
    return { agentId: 'recruiter', greeting: '', confidence: 0.85 }
  }

  // Intention juridique
  if (t.match(/contrat|juridique|loi|avocat|rgpd|conformité|litige/)) {
    return { agentId: 'legal', greeting: '', confidence: 0.85 }
  }

  // Intention analyse / reporting (rapports financiers → Claire)
  if (t.match(/données|kpi|analyse|tableau|statistique|métrique|rapport/)) {
    return { agentId: 'accounting', greeting: '', confidence: 0.8 }
  }

  // Intention connexion
  if (t.match(/connecter|intégrer|api|plateforme|outil|slack|gmail|stripe/)) {
    return { agentId: 'general', greeting: '', confidence: 0.8 }
  }

  // Default
  return {
    agentId: 'general',
    greeting: `Bonjour ${msg.userName.split(' ')[0]} ! Je peux vous aider sur :\n\n📈 Prospection & croissance\n📊 Comptabilité & trésorerie\n🎧 Support client\n👔 Recrutement\n⚖️ Juridique\n🎬 Contenu & vidéo\n🔌 Connecter vos outils\n\nDites-moi ce qui vous intéresse.`,
    confidence: 0.6,
  }
}

// ─── FORMATAGE PAR PLATEFORME ──────────────────────────────

/**
 * Adapte la réponse au format spécifique de chaque plateforme
 */
export function formatForChannel(text: string, channel: MessageChannel): string {
  switch (channel) {
    case 'whatsapp':
      return formatWhatsApp(text)
    case 'telegram':
      return formatTelegram(text)
    case 'messenger':
      return formatMessenger(text)
    default:
      return text
  }
}

function formatWhatsApp(text: string): string {
  return text
    .replace(/\*\*(.*?)\*\*/g, '*$1*') // Bold
    .replace(/__(.*?)__/g, '_$1_') // Italic
    .replace(/```([^`]+)```/g, '```$1```') // Code
    .replace(/^### (.*?)$/gm, '*$1*') // H3 → bold
    .replace(/^## (.*?)$/gm, '*$1*') // H2 → bold
    .replace(/^# (.*?)$/gm, '*$1*') // H1 → bold
}

function formatTelegram(text: string): string {
  return text // Telegram supporte le Markdown natif
}

function formatMessenger(text: string): string {
  return text
    .replace(/\*\*(.*?)\*\*/g, '$1') // Pas de bold
    .replace(/\n\n/g, '\n') // Compression
    .slice(0, 2000) // Limite Messenger
}

// ─── WEBHOOKS ──────────────────────────────────────────────

/**
 * WhatsApp Cloud API — Webhook Handler
 * Doc: https://developers.facebook.com/docs/whatsapp/cloud-api
 * 
 * Env vars: WHATSAPP_TOKEN, WHATSAPP_PHONE_ID
 */
export async function handleWhatsAppWebhook(body: any): Promise<IncomingMessage | null> {
  try {
    const entry = body?.entry?.[0]
    const change = entry?.changes?.[0]
    const msg = change?.value?.messages?.[0]

    if (!msg || msg.type !== 'text') return null

    return {
      channel: 'whatsapp',
      userId: msg.from,
      userName: change.value.contacts?.[0]?.profile?.name || 'Client',
      text: msg.text.body,
      timestamp: new Date(parseInt(msg.timestamp) * 1000).toISOString(),
      metadata: { phoneId: change.value.metadata?.phone_number_id || '' },
    }
  } catch {
    return null
  }
}

export async function sendWhatsApp(to: string, text: string): Promise<boolean> {
  const token = process.env.WHATSAPP_TOKEN
  const phoneId = process.env.WHATSAPP_PHONE_ID
  if (!token || !phoneId) return false

  try {
    const res = await fetch(`https://graph.facebook.com/v18.0/${phoneId}/messages`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messaging_product: 'whatsapp',
        to,
        type: 'text',
        text: { body: formatWhatsApp(text) },
      }),
    })
    return res.ok
  } catch {
    return false
  }
}

/**
 * Telegram Bot API — Webhook Handler
 * Doc: https://core.telegram.org/bots/api
 * 
 * Env var: TELEGRAM_BOT_TOKEN
 */
export async function handleTelegramWebhook(body: any): Promise<IncomingMessage | null> {
  try {
    const msg = body?.message
    if (!msg || !msg.text) return null

    return {
      channel: 'telegram',
      userId: String(msg.from?.id || ''),
      userName: msg.from?.first_name || 'Client',
      text: msg.text,
      timestamp: new Date(msg.date * 1000).toISOString(),
      metadata: { chatId: String(msg.chat?.id || '') },
    }
  } catch {
    return null
  }
}

export async function sendTelegram(chatId: string, text: string): Promise<boolean> {
  const token = process.env.TELEGRAM_BOT_TOKEN
  if (!token) return false

  try {
    const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: chatId,
        text,
        parse_mode: 'Markdown',
      }),
    })
    return res.ok
  } catch {
    return false
  }
}

/**
 * Messenger Platform — Webhook Handler
 * Doc: https://developers.facebook.com/docs/messenger-platform
 * 
 * Env var: MESSENGER_PAGE_TOKEN
 */
export async function handleMessengerWebhook(body: any): Promise<IncomingMessage | null> {
  try {
    const entry = body?.entry?.[0]
    const msg = entry?.messaging?.[0]
    if (!msg || !msg.message?.text) return null

    return {
      channel: 'messenger',
      userId: msg.sender?.id || '',
      userName: 'Client',
      text: msg.message.text,
      timestamp: new Date(msg.timestamp).toISOString(),
      metadata: { pageId: entry.id || '' },
    }
  } catch {
    return null
  }
}

export async function sendMessenger(userId: string, text: string): Promise<boolean> {
  const token = process.env.MESSENGER_PAGE_TOKEN
  if (!token) return false

  try {
    const res = await fetch(`https://graph.facebook.com/v18.0/me/messages?access_token=${token}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        recipient: { id: userId },
        message: { text: formatMessenger(text) },
      }),
    })
    return res.ok
  } catch {
    return false
  }
}

// ─── DISPATCHER UNIQUE ─────────────────────────────────────

/**
 * Point d'entrée unique pour tous les canaux
 */
export async function dispatchResponse(msg: IncomingMessage, response: string): Promise<boolean> {
  const formatted = formatForChannel(response, msg.channel)

  switch (msg.channel) {
    case 'whatsapp':
      return sendWhatsApp(msg.userId, formatted)
    case 'telegram':
      return sendTelegram(msg.metadata.chatId || msg.userId, formatted)
    case 'messenger':
      return sendMessenger(msg.userId, formatted)
    default:
      return false
  }
}
