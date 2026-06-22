// /workspace/hermes-saas/platform/src/app/api/vapi/create-call/route.ts
// API pour lancer un appel depuis ta plateforme
import { NextRequest, NextResponse } from 'next/server'

const VAPI_API_URL = 'https://api.vapi.ai'
const VAPI_API_KEY = process.env.VAPI_API_KEY || ''
const VAPI_ASSISTANT_ID = process.env.VAPI_ASSISTANT_ID || ''

export async function POST(req: NextRequest) {
  if (!VAPI_API_KEY) {
    return NextResponse.json(
      { error: 'Vapi API key not configured' },
      { status: 400 }
    )
  }

  const { phoneNumber, prospectName, context } = await req.json()

  if (!phoneNumber) {
    return NextResponse.json(
      { error: 'Numéro de téléphone requis' },
      { status: 400 }
    )
  }

  try {
    const response = await fetch(`${VAPI_API_URL}/call`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${VAPI_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        assistantId: VAPI_ASSISTANT_ID,
        phoneNumber,
        customer: {
          name: prospectName || 'Prospect',
        },
        // Contexte passé à l'assistant vocal
        variableValues: {
          context: context || '',
        },
        // Webhook pour recevoir le résultat
        webhookUrl: `${process.env.NEXT_PUBLIC_APP_URL}/api/vapi/webhook`,
      }),
    })

    const data = await response.json()

    // TODO: Sauvegarder l'appel dans Supabase
    return NextResponse.json({ success: true, callId: data.id })
  } catch (error) {
    console.error('Vapi call error:', error)
    return NextResponse.json(
      { error: 'Erreur lors du lancement de l\'appel' },
      { status: 500 }
    )
  }
}
