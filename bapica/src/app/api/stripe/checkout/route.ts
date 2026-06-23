import { NextRequest, NextResponse } from 'next/server'
import { stripe, PLANS, type PlanKey } from '@/lib/stripe'

// POST /api/stripe/checkout
// Body: { plan: 'starter' | 'pro' | 'business', userId, email }
// Crée une session Stripe Checkout (abonnement) et renvoie l'URL de paiement.
export async function POST(req: NextRequest) {
  try {
    const { plan, userId, email } = await req.json()

    if (!plan || !(plan in PLANS)) {
      return NextResponse.json({ error: 'Formule invalide' }, { status: 400 })
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
