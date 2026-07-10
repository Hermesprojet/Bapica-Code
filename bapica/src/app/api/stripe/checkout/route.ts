import { NextRequest, NextResponse } from 'next/server'
import { stripe, PLANS, type PlanKey } from '@/lib/stripe'
import { getSupabaseAdmin } from '@/lib/supabase-admin'

const corsHeaders = () => ({
  'Access-Control-Allow-Origin': 'https://bapica.com',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
})

export async function OPTIONS() {
  return NextResponse.json({}, { headers: corsHeaders() })
}

// POST /api/stripe/checkout
// Body: { plan: 'essential' | 'pro', userId, email }
// Crée une session Stripe Checkout (abonnement) et renvoie l'URL de paiement.
export async function POST(req: NextRequest) {
  try {
    const { plan } = await req.json()

    if (!plan || !(plan in PLANS)) {
      return NextResponse.json({ error: 'Formule invalide' }, { status: 400 })
    }

    // Récupérer l'utilisateur depuis le token (pas depuis le body !)
    const authHeader = req.headers.get('authorization')
    const token = authHeader?.replace('Bearer ', '')
    const supabaseAdmin = getSupabaseAdmin()
    
    let userId = ''
    let email = ''
    if (token) {
      const { data: { user } } = await supabaseAdmin.auth.getUser(token)
      if (user) {
        userId = user.id
        email = user.email || ''
      }
    }

    const planConfig = PLANS[plan as PlanKey]
    if (!planConfig.priceId) {
      return NextResponse.json(
        { error: `Prix Stripe non configuré pour la formule ${planConfig.name}.` },
        { status: 500 }
      )
    }

    const appUrl =
      process.env.NEXT_PUBLIC_APP_URL || req.nextUrl.origin

    const session = await stripe.checkout.sessions.create({
      mode: 'subscription',
      line_items: [{ price: planConfig.priceId, quantity: 1 }],
      client_reference_id: userId || undefined,
      customer_email: email || undefined,
      metadata: { plan, userId: userId || '' },
      subscription_data: { metadata: { plan, userId: userId || '' } },
      allow_promotion_codes: true,
      success_url: `${appUrl}/dashboard/billing?success=1`,
      cancel_url: `${appUrl}/dashboard/billing?canceled=1`,
    })

    return NextResponse.json({ url: session.url })
  } catch (error) {
    console.error('Stripe checkout error:', error)
    return NextResponse.json(
      { error: "Erreur lors de la création de la session de paiement." },
      { status: 500 }
    )
  }
}
