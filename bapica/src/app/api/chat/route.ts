import { NextRequest, NextResponse } from 'next/server'

// Route API centrale pour les agents
// POST /api/chat
// Body: { agentId, message, history }

export async function POST(req: NextRequest) {
  try {
    const { agentId, message, history } = await req.json()

    if (!agentId || !message) {
      return NextResponse.json(
        { error: 'agentId et message requis' },
        { status: 400 }
      )
    }

    // TODO: Vérifier l'abonnement de l'utilisateur
    // TODO: Vérifier le rate limiting

    // Charger le prompt système depuis le fichier correspondant
    const response = await callLLM(agentId, message, history)

    return NextResponse.json({ response, agentId })
  } catch (error) {
    console.error('Chat API error:', error)
    return NextResponse.json(
      { error: 'Erreur interne du serveur' },
      { status: 500 }
    )
  }
}

async function callLLM(
  agentId: string,
  message: string,
  history: { role: string; content: string }[]
): Promise<string> {
  // Ici, tu appelleras Claude API ou OpenAI API
  // Clés à récupérer depuis les variables d'environnement
  
  const apiKey = process.env.CLAUDE_API_KEY || process.env.OPENAI_API_KEY

  if (!apiKey) {
    return '⚠️ Agent non configuré. Veuillez ajouter une clé API Claude ou OpenAI dans les paramètres.'
  }

  // TODO: Implémenter l'appel API réel
  // Pour l'instant, réponse simulée
  return `Bonjour ! Je suis l'agent ${agentId}. Votre message a bien été reçu : "${message}". La connexion à l'API IA sera active dès que vous aurez configuré votre clé API.`
}
