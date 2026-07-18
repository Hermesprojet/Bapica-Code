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

// Accepte les deux conventions de nommage des variables d'env de prix Stripe
// (STRIPE_PRICE_PRO ou STRIPE_PRO_PRICE_ID) pour éviter toute incohérence.
const priceId = (plan: 'ESSENTIAL' | 'PRO') =>
  process.env[`STRIPE_PRICE_${plan}`] ||
  process.env[`STRIPE_${plan}_PRICE_ID`] ||
  ''

export const PLANS = {
  essential: {
    name: 'Essentiel',
    priceId: priceId('ESSENTIAL'),
    price: 49,
    agents: 8,
    messagesPerMonth: -1, // illimité
    voiceMinutes: 0,
    voiceRate: 0.20, // €/min
  },
  pro: {
    name: 'Pro',
    priceId: priceId('PRO'),
    price: 79,
    agents: 10,
    messagesPerMonth: -1, // illimité
    voiceMinutes: 0,
    voiceRate: 0.20, // €/min
  },
}

export type PlanKey = keyof typeof PLANS

// Retrouve la formule à partir d'un identifiant de prix Stripe (utilisé par le webhook).
export function planFromPriceId(id: string | null | undefined): PlanKey | null {
  if (!id) return null
  const entry = (Object.keys(PLANS) as PlanKey[]).find(
    (k) => PLANS[k].priceId === id
  )
  return entry ?? null
}
