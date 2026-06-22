'use client'

import { useState, useEffect } from 'react'
import { CreditCard, Check, Loader2, ArrowUpDown } from 'lucide-react'
import { PLANS, type PlanKey } from '@/lib/stripe'

const planOrder: PlanKey[] = ['starter', 'pro', 'business']

const planDetails = {
  starter: { name: 'Starter', price: 29, agents: 3, messages: 1000, mins: 0, popular: false },
  pro: { name: 'Pro', price: 59, agents: 7, messages: 5000, mins: 60, popular: true },
  business: { name: 'Business', price: 99, agents: 12, messages: -1, mins: 300, popular: false },
}

export default function BillingPage() {
  const [currentPlan, setCurrentPlan] = useState<PlanKey>('starter')

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Abonnement</h1>
        <p className="mt-1 text-muted-foreground">
          Gérez votre forfait et vos moyens de paiement.
        </p>
      </div>

      {/* Current plan info */}
      <div className="mb-8 rounded-xl border border-border bg-card p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Forfait actuel</p>
            <p className="text-2xl font-bold">{planDetails[currentPlan].name}</p>
            <p className="text-sm text-muted-foreground">
              {planDetails[currentPlan].price}€ / mois
            </p>
          </div>
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
            <CreditCard className="h-6 w-6 text-primary" />
          </div>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-4 border-t border-border pt-4 text-center text-sm">
          <div>
            <p className="font-semibold">{planDetails[currentPlan].agents}</p>
            <p className="text-muted-foreground">Agents</p>
          </div>
          <div>
            <p className="font-semibold">
              {planDetails[currentPlan].messages === -1
                ? '∞'
                : `${planDetails[currentPlan].messages.toLocaleString()}`}
            </p>
            <p className="text-muted-foreground">Messages/mois</p>
          </div>
          <div>
            <p className="font-semibold">
              {planDetails[currentPlan].mins === 0 ? '0' : `${planDetails[currentPlan].mins}min`}
            </p>
            <p className="text-muted-foreground">Appels vocaux</p>
          </div>
        </div>
      </div>

      {/* All plans */}
      <div className="grid gap-6 lg:grid-cols-3">
        {planOrder.map((key) => {
          const plan = planDetails[key]
          return (
            <div
              key={key}
              className={`relative rounded-xl border p-6 ${
                key === currentPlan
                  ? 'border-primary bg-primary/5'
                  : 'border-border bg-card'
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-primary px-3 py-0.5 text-xs font-semibold text-primary-foreground">
                  Populaire
                </div>
              )}

              <h3 className="text-lg font-bold">{plan.name}</h3>
              <p className="mt-2 text-3xl font-bold">{plan.price}€<span className="text-sm font-normal text-muted-foreground">/mois</span></p>

              <ul className="mt-6 space-y-2 text-sm">
                <li className="flex items-center gap-2">
                  <Check className="h-4 w-4 text-green-500" />
                  {plan.agents} agents IA
                </li>
                <li className="flex items-center gap-2">
                  <Check className="h-4 w-4 text-green-500" />
                  {plan.messages === -1 ? 'Messages illimités' : `${plan.messages.toLocaleString()} messages/mois`}
                </li>
                <li className="flex items-center gap-2">
                  <Check className="h-4 w-4 text-green-500" />
                  {plan.mins === 0 ? 'Sans appels vocaux' : `${plan.mins} min d'appels/mois`}
                </li>
                <li className="flex items-center gap-2">
                  <Check className="h-4 w-4 text-green-500" />
                  Multilingue FR/EN/AR
                </li>
              </ul>

              {key !== currentPlan && (
                <button className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-medium hover:bg-muted transition-colors">
                  <ArrowUpDown className="h-4 w-4" />
                  {key > currentPlan ? 'Passer à' : 'Revenir à'} {plan.name}
                </button>
              )}

              {key === currentPlan && (
                <div className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg bg-primary/10 px-4 py-2.5 text-sm font-medium text-primary">
                  <Check className="h-4 w-4" />
                  Plan actuel
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
