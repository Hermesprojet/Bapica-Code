import Stripe from 'stripe'

export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY || '', {
  apiVersion: '2024-11-20.acacia',
  typescript: true,
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
