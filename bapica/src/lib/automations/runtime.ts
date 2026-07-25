// Moteur d'exécution des automatisations — boucle d'outils AUTONOME.
// À la différence du chat (« propose → le client valide »), une automatisation a DÉJÀ été
// validée par le client : ses outils d'envoi/action s'exécutent RÉELLEMENT. Isolé du chat
// (aucun impact sur /api/chat) ; couvre les cas récurrents (relances, publications, docs…).

import Anthropic from '@anthropic-ai/sdk'
import { getAgentById } from '@/lib/agents'
import { getSystemPromptForAgent } from '@/lib/agent-prompts'
import { executeAction } from '@/lib/actions/execute'
import { proposeEmailTool } from '@/lib/tools/email-tools'
import { proposeSmsTool } from '@/lib/tools/sms-tools'
import { proposeActionTool, listPlatformsTool, readPlatformTool, listClientPlatforms, readFromPlatform } from '@/lib/tools/platform-call'
import { proposeDocumentTool } from '@/lib/tools/document-tools'
import { buildDeliverable, type DeliverableKind } from '@/lib/deliverables'
import { createDeliverable } from '@/lib/deliverables/store'
import { tagInteractionTool } from '@/lib/tools/tag-tools'
import { createTag } from '@/lib/tags/store'
import { readBankTool } from '@/lib/tools/bank-tools'
import { readBalances, readTransactions } from '@/lib/bank/gocardless'
import { webSearchTool, analyzeCompanyTool } from '@/lib/tools/research-tools'
import { webSearch, researchCompany } from '@/lib/company-research'
import { auditSiteTool, auditSite } from '@/lib/tools/seo-audit'

const AUTONOMY_NOTE =
  "\n\n--- MODE AUTOMATISATION ---\n" +
  "Tu exécutes une automatisation que le client a DÉJÀ validée. Réalise la tâche de bout en bout : " +
  "tes outils d'envoi et d'action (proposer_email, proposer_sms, proposer_action) s'exécutent RÉELLEMENT " +
  "(pas de validation supplémentaire à demander). Sois précis et sobre. À la fin, résume en quelques " +
  "phrases ce que tu as concrètement fait (envois, publications, documents créés). " +
  "FORMAT DES DOCUMENTS : produis-les en PDF (rapports, notes, synthèses) ou en Excel/CSV (données " +
  "chiffrées, tableaux) — JAMAIS en markdown ou texte brut, peu lisibles pour le client."

/**
 * Exécute une automatisation : fait tourner l'agent responsable sur la consigne, avec ses
 * outils en mode autonome. Renvoie un résumé texte de ce qui a été réalisé.
 */
export async function runAutomationAgent(opts: {
  agentId: string
  task: string
  userId: string
  context: string
}): Promise<string> {
  const apiKey = process.env.ANTHROPIC_API_KEY
  if (!apiKey) return 'ANTHROPIC_API_KEY manquante.'
  const agent = getAgentById(opts.agentId) || getAgentById('general')!
  const client = new Anthropic({ apiKey })

  const system =
    `Tu es ${agent.persona}, ${agent.name} chez Bapica.\n${getSystemPromptForAgent(agent.id)}` +
    (opts.context ? `\n\n--- Contexte du client ---\n${opts.context}` : '') +
    AUTONOMY_NOTE

  const tools = [
    proposeEmailTool, proposeSmsTool, proposeActionTool, listPlatformsTool, readPlatformTool,
    proposeDocumentTool, tagInteractionTool, readBankTool, webSearchTool, analyzeCompanyTool, auditSiteTool,
  ] as unknown as any[]

  const messages: Anthropic.MessageParam[] = [{ role: 'user', content: opts.task.slice(0, 4000) }]
  const done: string[] = []

  let response = await client.messages.create({
    model: 'claude-sonnet-4-5', max_tokens: 2500, temperature: 0.4,
    system: system.slice(0, 12000), tools, messages,
  })

  for (let round = 0; round < 4; round++) {
    const toolUses = response.content.filter((b): b is Anthropic.ToolUseBlock => b.type === 'tool_use')
    if (toolUses.length === 0) break
    const toolResults: Anthropic.ToolResultBlockParam[] = []
    for (const tool of toolUses) {
      let result = ''
      try {
        const i = tool.input as any
        if (tool.name === 'proposer_email') {
          const r = await executeAction(opts.userId, { provider: 'email', method: 'SEND', path: '', body: { to: String(i?.to || ''), subject: String(i?.subject || ''), text: String(i?.text || '') } })
          if (r.ok) done.push(`Email → ${i?.to}`)
          result = JSON.stringify(r.ok ? { ok: true, statut: 'envoyé' } : { ok: false, erreur: r.error })
        } else if (tool.name === 'proposer_sms') {
          const r = await executeAction(opts.userId, { provider: 'sms', method: 'SEND', path: '', body: { to: String(i?.to || ''), text: String(i?.text || '') } })
          if (r.ok) done.push(`SMS → ${i?.to}`)
          result = JSON.stringify(r.ok ? { ok: true, statut: 'envoyé' } : { ok: false, erreur: r.error })
        } else if (tool.name === 'proposer_action') {
          const r = await executeAction(opts.userId, { provider: String(i?.provider || ''), method: String(i?.method || 'POST'), path: String(i?.path || '/'), body: i?.body })
          if (r.ok) done.push(`Action ${i?.provider} ${i?.method} ${i?.path}`)
          result = JSON.stringify(r.ok ? { ok: true, resultat: r.result } : { ok: false, erreur: r.error })
        } else if (tool.name === 'proposer_document') {
          const kind = (['pdf', 'excel', 'csv', 'markdown', 'text'].includes(String(i?.kind)) ? i.kind : 'pdf') as DeliverableKind
          const file = buildDeliverable({ kind, title: String(i?.title || 'Document'), content: i?.content != null ? String(i.content) : undefined, columns: Array.isArray(i?.columns) ? i.columns.map(String) : undefined, rows: Array.isArray(i?.rows) ? i.rows : undefined })
          await createDeliverable({ userId: opts.userId, agentId: agent.id, kind, title: String(i?.title || 'Document'), filename: file.filename, mime: file.mime, content: file.content }).catch(() => {})
          done.push(`Document « ${i?.title} »`)
          result = JSON.stringify({ ok: true, statut: 'créé' })
        } else if (tool.name === 'etiqueter_echange') {
          await createTag({ userId: opts.userId, agentId: agent.id, tag: String(i?.tag || 'autre'), contact: i?.contact ? String(i.contact) : undefined, channel: i?.channel ? String(i.channel) : undefined, note: i?.note ? String(i.note) : undefined }).catch(() => {})
          result = JSON.stringify({ ok: true })
        } else if (tool.name === 'lister_plateformes') {
          result = JSON.stringify({ plateformes: await listClientPlatforms(opts.userId) })
        } else if (tool.name === 'lire_plateforme') {
          const r = await readFromPlatform(opts.userId, String(i?.provider || ''), String(i?.path || '/'))
          result = JSON.stringify(r.ok ? { ok: true, donnees: r.data } : { ok: false, erreur: r.error })
        } else if (tool.name === 'lire_banque') {
          const r = i?.action === 'transactions' ? await readTransactions(opts.userId) : await readBalances(opts.userId)
          result = JSON.stringify(r.ok ? { ok: true, donnees: (r as any).transactions || (r as any).balances } : { ok: false, erreur: r.error })
        } else if (tool.name === 'rechercher_web') {
          const r = await webSearch(String(i?.query || ''))
          result = JSON.stringify({ ok: true, resultats: r.slice(0, 8) })
        } else if (tool.name === 'analyser_entreprise') {
          const r = await researchCompany({ companyName: String(i?.companyName || ''), website: i?.website ? String(i.website) : undefined, sector: i?.sector ? String(i.sector) : undefined, city: i?.city ? String(i.city) : undefined })
          result = JSON.stringify({ ok: true, profil: r.summary })
        } else if (tool.name === 'auditer_site') {
          const r = await auditSite(String(i?.url || ''))
          result = JSON.stringify(r.ok ? { ok: true, audit: r.audit } : { ok: false, erreur: r.error })
        } else {
          result = JSON.stringify({ ok: false, erreur: `Outil ${tool.name} indisponible en automatisation.` })
        }
      } catch (e) {
        result = JSON.stringify({ ok: false, erreur: String(e instanceof Error ? e.message : e) })
      }
      toolResults.push({ type: 'tool_result', tool_use_id: tool.id, content: result })
    }
    messages.push({ role: 'assistant', content: response.content }, { role: 'user', content: toolResults })
    response = await client.messages.create({
      model: 'claude-sonnet-4-5', max_tokens: 2500, temperature: 0.4,
      system: system.slice(0, 12000), tools, messages,
    })
  }

  const text = response.content.filter((b): b is Anthropic.TextBlock => b.type === 'text').map((b) => b.text).join('\n').trim()
  const summary = done.length ? `\n\nActions réalisées : ${done.join(' · ')}` : ''
  return (text || 'Automatisation exécutée.') + summary
}
