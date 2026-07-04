import { NextRequest, NextResponse } from 'next/server'
import type Stripe from 'stripe'
import { stripe, planFromPriceId, type PlanKey } from '@/lib/stripe'
import { getSupabaseAdmin } from '@/lib/supabase-admin'

const planLimits: Record<PlanKey, number> = {
  essential: -1,
  pro: -1,
}

async function setPlan(
  userId: string,
  plan: PlanKey,
  fields: { customerId?: string; subscriptionId?: string | null }
) {
  const supabase = getSupabaseAdmin()
  await supabase
    .from('profiles')
    .update({
      plan,
      ...(fields.customerId ? { stripe_customer_id: fields.customerId } : {}),
      ...(fields.subscriptionId !== undefined
        ? { stripe_subscription_id: fields.subscriptionId }
        : {}),
      updated_at: new Date().toISOString(),
    })
    .eq('id', userId)
}

export async function POST(req: NextRequest) {
  const body = await req.text()
  const signature = req.headers.get('stripe-signature') || ''

  let event: Stripe.Event
  try {
    event = stripe.webhooks.constructEvent(
      body,
      signature,
      process.env.STRIPE_WEBHOOK_SECRET || ''
    )
  } catch {
    return NextResponse.json({ error: 'Invalid signature' }, { status: 400 })
  }

  try {
    switch (event.type) {
      case 'checkout.session.completed': {
        const session = event.data.object as Stripe.Checkout.Session
        const userId =
          session.client_reference_id || session.metadata?.userId || ''
        const plan = (session.metadata?.plan as PlanKey) || 'essential'
        if (userId) {
          await setPlan(userId, plan, {
            customerId:
              typeof session.customer === 'string'
                ? session.customer
                : undefined,
            subscriptionId:
              typeof session.subscription === 'string'
                ? session.subscription
                : undefined,
          })
        }
        break
      }

      case 'customer.subscription.updated': {
        const sub = event.data.object as Stripe.Subscription
        const userId = sub.metadata?.userId || ''
        const priceId = sub.items.data[0]?.price.id
        const plan = planFromPriceId(priceId) || (sub.metadata?.plan as PlanKey)
        if (userId && plan) {
          await setPlan(userId, plan, {
            customerId:
              typeof sub.customer === 'string' ? sub.customer : undefined,
            subscriptionId: sub.id,
          })
        }
        break
      }

      case 'customer.subscription.deleted': {
        const sub = event.data.object as Stripe.Subscription
        const userId = sub.metadata?.userId || ''
        if (userId) {
          // Résiliation : on repasse l'utilisateur en formule Essentiel.
          await setPlan(userId, 'essential', { subscriptionId: null })
        }
        break
      }
    }
  } catch (error) {
    console.error('Stripe webhook handling error:', error)
    return NextResponse.json({ error: 'Handler error' }, { status: 500 })
  }

  return NextResponse.json({ received: true })
}
