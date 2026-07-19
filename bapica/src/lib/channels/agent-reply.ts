import Anthropic from '@anthropic-ai/sdk'
import { getSupabaseAdmin } from '@/lib/supabase-admin'
import { getAgentById } from '@/lib/agents'
import { getSystemPromptForAgent } from '@/lib/agent-prompts'
import { buildBusinessBrief } from '@/lib/business-context'

// Mappe le modèle déclaré de l'agent vers un ID Claude valide (cf. resolveModel du chat).
function validModel(agentModel: string): string {
  if (agentModel.startsWith('claude-opus')) return 'claude-opus-4-1'
  if (agentModel.startsWith('claude-haiku')) return 'claude-haiku-4-5'
  return 'claude-sonnet-4-5'
}

/**
 * Génère la réponse d'un agent pour un client identifié (par son user_id), en
 * injectant le contexte de SON entreprise (onboarding). Version « connectée » du
 * traitement, à la place de demo-chat quand le webhook a résolu le locataire.
 */
export async function replyForUser(userId: string, agentId: string, text: string): Promise<string> {
  const apiKey = process.env.ANTHROPIC_API_KEY
  if (!apiKey) return 'Le service est momentanément indisponible. Réessayez dans un instant.'

  const agent = getAgentById(agentId) || getAgentById('general')!

  // Contexte business du client (service_role, sans session utilisateur).
  let brief = ''
  try {
    const db = getSupabaseAdmin()
    const { data } = await db.auth.admin.getUserById(userId)
    brief = buildBusinessBrief(data?.user?.user_metadata?.onboarding_data)
  } catch {
    /* pas de contexte : on répond quand même */
  }

  const system =
    `Tu es ${agent.persona}, ${agent.name} chez Bapica.\n` +
    `${getSystemPromptForAgent(agent.id)}` +
    (brief ? `\n\n--- Entreprise du client ---\n${brief}` : '') +
    `\n\nRéponds de façon concrète et concise (4 à 6 phrases), dans la langue du message. Pas de Markdown brut ni d'émojis superflus.`

  try {
    const client = new Anthropic({ apiKey, timeout: 20000 })
    const completion = await client.messages.create({
      model: validModel(agent.model),
      max_tokens: Math.min(agent.maxTokens || 800, 800),
      temperature: agent.temperature ?? 0.5,
      system: system.slice(0, 6000),
      messages: [{ role: 'user', content: text.slice(0, 1000) }],
    })
    const out = completion.content
      .filter((b): b is Anthropic.TextBlock => b.type === 'text')
      .map((b) => b.text)
      .join('\n')
      .trim()
    return out || "Désolé, je n'ai pas pu générer de réponse."
  } catch (e) {
    console.error('replyForUser error:', String(e))
    return 'Désolé, une erreur est survenue. Réessayez dans un instant.'
  }
}
