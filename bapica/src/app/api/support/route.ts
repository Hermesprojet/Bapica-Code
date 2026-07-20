import { NextRequest, NextResponse } from 'next/server'
import Anthropic from '@anthropic-ai/sdk'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { SUPPORT_KB } from '@/lib/support-kb'

/**
 * POST /api/support — assistant d'aide Bapica (comment utiliser la plateforme).
 * Distinct des agents métier : il répond sur le PRODUIT lui-même.
 * Auth : Bearer Supabase (réservé aux clients connectés).
 */
interface Msg { role: 'user' | 'assistant'; content: string }

export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  let body: any = {}
  try { body = await req.json() } catch { return NextResponse.json({ error: 'Requête invalide.' }, { status: 400 }) }

  const message = typeof body.message === 'string' ? body.message.trim() : ''
  if (!message) return NextResponse.json({ error: 'Message requis.' }, { status: 400 })

  const apiKey = process.env.ANTHROPIC_API_KEY
  if (!apiKey) {
    return NextResponse.json({ error: 'Assistance momentanément indisponible (configuration).' }, { status: 503 })
  }

  const history: Msg[] = Array.isArray(body.history)
    ? body.history
        .filter((m: any) => (m?.role === 'user' || m?.role === 'assistant') && typeof m?.content === 'string' && m.content.trim())
        .slice(-6)
    : []

  const system = `Tu es l'assistant d'aide de Bapica. Tu aides les CLIENTS à utiliser la plateforme :
où cliquer, comment configurer, que faire quand quelque chose ne marche pas.

${SUPPORT_KB}

RÈGLES :
- Réponds uniquement à partir des informations ci-dessus. Si tu ne sais pas, dis-le simplement et
  invite à contacter l'équipe Bapica — n'invente jamais une fonctionnalité, un menu ou un bouton.
- Sois bref et concret : indique le chemin exact dans l'interface (ex : « Canaux → bloc Telegram »).
- Prose naturelle, pas de Markdown (ni #, ni **, ni listes à puces), pas d'émojis : le texte
  s'affiche tel quel dans une bulle.
- Trois à six phrases maximum, sauf si l'utilisateur demande une procédure détaillée.
- Réponds dans la langue de l'utilisateur, avec un ton clair et rassurant.
- Tu n'exécutes aucune action et tu ne demandes jamais de mot de passe ni de clé API.`

  try {
    const client = new Anthropic({ apiKey, timeout: 20000 })
    const completion = await client.messages.create({
      model: 'claude-haiku-4-5',
      max_tokens: 600,
      temperature: 0.3,
      system,
      messages: [
        ...history.map((m) => ({ role: m.role, content: m.content })),
        { role: 'user' as const, content: message.slice(0, 1000) },
      ],
    })

    const text = completion.content
      .filter((b): b is Anthropic.TextBlock => b.type === 'text')
      .map((b) => b.text)
      .join('\n')
      .trim()

    return NextResponse.json({ response: text || "Je n'ai pas de réponse à cette question pour le moment." })
  } catch (e) {
    console.error('Support chat error:', String(e))
    return NextResponse.json({ error: 'Assistance momentanément indisponible.' }, { status: 502 })
  }
}
