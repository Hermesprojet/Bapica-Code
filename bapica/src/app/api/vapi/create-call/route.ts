// API pour lancer un appel vocal sortant via Vapi
// POST /api/vapi/create-call
// Body: { phoneNumber, prospectName?, context? }
import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

const corsHeaders = () => ({
  'Access-Control-Allow-Origin': 'https://bapica.com',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
})

export async function OPTIONS() {
  return NextResponse.json({}, { headers: corsHeaders() })
}

const VAPI_API_URL = 'https://api.vapi.ai'

export async function POST(req: NextRequest) {
  // Vérifier l'authentification
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL || '',
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '',
    { auth: { persistSession: false, autoRefreshToken: false } }
  )
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) {
    return NextResponse.json({ error: 'Non authentifié' }, { status: 401 })
  }

  const VAPI_API_KEY = process.env.VAPI_API_KEY || ''
  const VAPI_ASSISTANT_ID = process.env.VAPI_ASSISTANT_ID || ''
  // Numéro Vapi utilisé comme appelant (à configurer dans le dashboard Vapi).
  const VAPI_PHONE_NUMBER_ID = process.env.VAPI_PHONE_NUMBER_ID || ''

  if (!VAPI_API_KEY || !VAPI_ASSISTANT_ID || !VAPI_PHONE_NUMBER_ID) {
    return NextResponse.json(
      {
        error:
          'Configuration Vapi incomplète (VAPI_API_KEY, VAPI_ASSISTANT_ID, VAPI_PHONE_NUMBER_ID).',
      },
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
        phoneNumberId: VAPI_PHONE_NUMBER_ID,
        customer: {
          number: phoneNumber,
          name: prospectName || 'Prospect',
        },
        // Variables transmises à l'assistant vocal (contexte du prospect).
        assistantOverrides: {
          variableValues: {
            prospectName: prospectName || 'Prospect',
            context: context || '',
          },
        },
      }),
    })

    const data = await response.json()

    if (!response.ok) {
      console.error('Vapi call error:', data)
      return NextResponse.json(
        { error: data?.message || "Erreur lors du lancement de l'appel." },
        { status: 502 }
      )
    }

    // Sauvegarder l'appel dans Supabase
    try {
      const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || ""
      const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ""
      if (supabaseUrl && supabaseKey) {
        const { createClient } = await import("@supabase/supabase-js")
        const supabase = createClient(supabaseUrl, supabaseKey)
        await supabase.from("vapi_calls").insert({ call_id: data.id, phone_number: phoneNumber, assistant_id: VAPI_ASSISTANT_ID, created_at: new Date().toISOString(), user_id: user?.id })
      }
    } catch (e) {
      console.error("Vapi call save failed:", e)
    }
    return NextResponse.json({ success: true, callId: data.id })
  } catch (error) {
    console.error('Vapi call error:', error)
    return NextResponse.json(
      { error: "Erreur lors du lancement de l'appel." },
      { status: 500 }
    )
  }
}
