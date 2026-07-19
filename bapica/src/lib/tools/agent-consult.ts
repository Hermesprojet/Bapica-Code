import Anthropic from '@anthropic-ai/sdk'
import AGENTS, { getAgentById } from '@/lib/agents'
import { getSystemPromptForAgent } from '@/lib/agent-prompts'

/**
 * Outil de collaboration inter-agents : un agent peut consulter un confrère
 * (ex : Camille demande à Marc l'analyse concurrentielle, ou à Léo le profil du
 * client) au lieu d'interroger l'utilisateur. Le confrère répond avec le MÊME
 * contexte client, en interne — l'utilisateur ne voit que la réponse finale.
 */
export const consultAgentTool = {
  name: 'consulter_agent',
  description:
    "Consulte un autre agent Bapica pour obtenir une information ou un avis d'expert AVANT de poser une question au client. " +
    'Exemples : demander à marc le marché et les concurrents, à general (Léo) le profil global et les priorités, ' +
    "à accounting (Claire) les chiffres, à support (Sofia) l'historique client. " +
    "Utilise cet outil dès qu'une information te manque, plutôt que d'interroger l'utilisateur.",
  input_schema: {
    type: 'object' as const,
    properties: {
      agent_id: {
        type: 'string',
        enum: AGENTS.map((a) => a.id),
        description: "Identifiant de l'agent à consulter",
      },
      question: {
        type: 'string',
        description: 'La question précise posée à cet agent confrère',
      },
    },
    required: ['agent_id', 'question'],
  },
}

/**
 * Exécute la consultation : fait répondre l'agent cible avec le contexte client,
 * en interne (réponse courte et factuelle, destinée à un confrère).
 */
export async function runAgentConsult(
  client: Anthropic,
  agentId: string,
  question: string,
  clientContext: string
): Promise<string> {
  const target = getAgentById(agentId)
  if (!target) return `Agent "${agentId}" inconnu.`

  const system =
    `Tu es ${target.persona}, ${target.name} chez Bapica.\n` +
    `${getSystemPromptForAgent(target.id)}\n` +
    (clientContext ? `\n--- Contexte du client ---\n${clientContext}\n` : '') +
    `\nUn AGENT CONFRÈRE te consulte en interne (ce n'est pas le client). ` +
    `Réponds de façon factuelle et dense, en 3 à 6 phrases, en te limitant à ton domaine d'expertise. ` +
    `Pas de formule de politesse, pas de question en retour : donne l'information utile. ` +
    `Si tu ne disposes pas de l'information, dis-le en une phrase.`

  try {
    const completion = await client.messages.create({
      model: 'claude-haiku-4-5',
      max_tokens: 500,
      temperature: 0.3,
      system: system.slice(0, 6000),
      messages: [{ role: 'user', content: question.slice(0, 800) }],
    })
    const text = completion.content
      .filter((b): b is Anthropic.TextBlock => b.type === 'text')
      .map((b) => b.text)
      .join('\n')
      .trim()
    return text || "Pas d'information disponible."
  } catch (e) {
    return `Consultation impossible (${String(e instanceof Error ? e.message : e)}).`
  }
}
