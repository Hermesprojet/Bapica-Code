import { NextRequest, NextResponse } from 'next/server'
import { stripe } from '@/lib/stripe'
import { getSupabaseAdmin } from '@/lib/supabase-admin'

const corsHeaders = () => ({
  'Access-Control-Allow-Origin': 'https://bapica.com',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
})

export async function OPTIONS() {
  return NextResponse.json({}, { headers: corsHeaders() })
}

// POST /api/stripe/portal
// Body: { userId }
// Ouvre le portail de facturation Stripe pour gérer/résilier l'abonnement.
export async function POST(req: NextRequest) {
  try {
    // Récupérer l'utilisateur depuis le token Supabase (pas depuis le body !)
    const authHeader = req.headers.get('authorization')
    const token = authHeader?.replace('Bearer ', '')
    if (!token) {
      return NextResponse.json({ error: 'Non authentifié' }, { status: 401 })
    }

    const supabase = getSupabaseAdmin()
    const { data: { user }, error: authError } = await supabase.auth.getUser(token)
    if (authError || !user) {
      return NextResponse.json({ error: 'Non authentifié' }, { status: 401 })
    }

    const userId = user.id
    const { data: profile } = await supabase
      .from('profiles')
      .select('stripe_customer_id')
      .eq('id', userId)
      .maybeSingle()

    if (!profile?.stripe_customer_id) {
      // Pas d'abonnement Stripe : on renvoie une réponse « douce » (200) avec un
      // indicateur exploité par le frontend pour proposer de souscrire, plutôt
      // qu'une erreur générique.
      return NextResponse.json({
        noSubscription: true,
        error:
          'Aucun abonnement actif. Souscrivez à une formule depuis la page facturation.',
      })
    }

    const appUrl = process.env.NEXT_PUBLIC_APP_URL || req.nextUrl.origin
    const session = await stripe.billingPortal.sessions.create({
      customer: profile.stripe_customer_id,
      return_url: `${appUrl}/dashboard/billing`,
    })

    return NextResponse.json({ url: session.url })
  } catch (error) {
    console.error('Stripe portal error:', error)
    return NextResponse.json(
      { error: "Erreur lors de l'ouverture du portail de facturation." },
      { status: 500 }
    )
  }
}
