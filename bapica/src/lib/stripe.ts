import Stripe from 'stripe'

// Instanciation paresseuse : le client Stripe n'est construit qu'à la
// première utilisation (au moment d'une requête), pas à l'import du module.
// Cela évite que le build échoue lorsque STRIPE_SECRET_KEY est absente,
// car le SDK Stripe lève une erreur si aucune clé n'est fournie.
let stripeClient: Stripe | null = null

function getStripe(): Stripe {
  if (!stripeClient) {
    stripeClient = new Stripe(process.env.STRIPE_SECRET_KEY || '', {
      apiVersion: '2025-02-24.acacia',
      typescript: true,
    })
  }
  return stripeClient
}

export const stripe = new Proxy({} as Stripe, {
  get(_target, prop) {
    return Reflect.get(getStripe(), prop, getStripe())
  },
})

export const PLANS = {
  starter: {
    name: 'Starter',
    priceId: process.env.STRIPE_STARTER_PRICE_ID || '',
    price: 29,
    agents: 3,
    messagesPerMonth: 1000,
    voiceMinutes: 0,
  },
  pro: {
    name: 'Pro',
    priceId: process.env.STRIPE_PRO_PRICE_ID || '',
    price: 59,
    agents: 7,
    messagesPerMonth: 5000,
    voiceMinutes: 60,
  },
  business: {
    name: 'Business',
    priceId: process.env.STRIPE_BUSINESS_PRICE_ID || '',
    price: 99,
    agents: 11,
    messagesPerMonth: -1, // illimité
    voiceMinutes: 300,
  },
} as const

export type PlanKey = keyof typeof PLANS
