'use client'

import { useState, useEffect } from 'react'
import { CreditCard, Check, Loader2, ArrowUpDown, Settings } from 'lucide-react'
import { type PlanKey } from '@/lib/stripe'
import { supabase } from '@/lib/supabase'

const planOrder: PlanKey[] = ['essential', 'pro']

const planDetails = {
  essential: { name: 'Essentiel', price: 49, agents: 8, popular: false },
  pro: { name: 'Pro', price: 79, agents: 10, popular: true },
}

export default function BillingPage() {
  const [currentPlan, setCurrentPlan] = useState<PlanKey>('essential')
  const [userId, setUserId] = useState<string | null>(null)
  const [email, setEmail] = useState<string | null>(null)
  const [loadingPlan, setLoadingPlan] = useState<PlanKey | null>(null)
  const [portalLoading, setPortalLoading] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    // Bandeau retour de paiement
    const params = new URLSearchParams(window.location.search)
    if (params.get('success')) setNotice('✓ Paiement confirmé. Votre formule sera mise à jour sous quelques instants.')
    if (params.get('canceled')) setNotice('Paiement annulé. Aucun changement effectué.')

    // Récupère l'utilisateur et sa formule actuelle
    supabase.auth.getUser().then(async ({ data }) => {
      const user = data.user
      if (!user) return
      setUserId(user.id)
      setEmail(user.email ?? null)
      const { data: profile } = await supabase
        .from('profiles')
        .select('plan')
        .eq('id', user.id)
        .single()
      if (profile?.plan && planOrder.includes(profile.plan as PlanKey)) {
        setCurrentPlan(profile.plan as PlanKey)
      }
    })
  }, [])

  const handleCheckout = async (plan: PlanKey) => {
    setLoadingPlan(plan)
    try {
      const res = await fetch('/api/stripe/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan, userId, email }),
      })
      const data = await res.json()
      if (data.url) {
        window.location.href = data.url
      } else {
        setNotice(data.error || 'Erreur lors du paiement.')
        setLoadingPlan(null)
      }
    } catch {
      setNotice('Erreur réseau. Veuillez réessayer.')
      setLoadingPlan(null)
    }
  }

  const handlePortal = async () => {
    setPortalLoading(true)
    try {
      const res = await fetch('/api/stripe/portal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId }),
      })
      const data = await res.json()
      if (data.url) {
        window.location.href = data.url
      } else if (data.noSubscription) {
        // Pas encore d'abonnement Stripe : on invite à souscrire au lieu
        // d'afficher une erreur générique.
        setNotice(
          "Vous n'avez pas encore d'abonnement Stripe. Souscrivez à un plan ci-dessous."
        )
        setPortalLoading(false)
      } else {
        setNotice(data.error || "Impossible d'ouvrir le portail.")
        setPortalLoading(false)
      }
    } catch {
      setNotice('Erreur réseau. Veuillez réessayer.')
      setPortalLoading(false)
    }
  }

  return (
    <div>
      <div className="reveal mb-8">
        <h1 className="text-2xl font-bold">Abonnement</h1>
        <p className="mt-1 text-muted-foreground">
          Gérez votre forfait et vos moyens de paiement.
        </p>
      </div>

      {notice && (
        <div className="mb-6 rounded-lg border border-border bg-muted/50 p-4 text-sm">
          {notice}
        </div>
      )}

      {/* Current plan info */}
      <div className="reveal mb-8 rounded-xl border border-border bg-card p-6" style={{ animationDelay: '60ms' }}>
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
        <div className="mt-4 grid grid-cols-2 gap-4 border-t border-border pt-4 text-center text-sm">
          <div>
            <p className="font-semibold">{planDetails[currentPlan].agents}</p>
            <p className="text-muted-foreground">Agents IA</p>
          </div>
          <div>
            <p className="font-semibold">∞</p>
            <p className="text-muted-foreground">Messages illimités</p>
          </div>
        </div>
        <button
          onClick={handlePortal}
          disabled={portalLoading || !userId}
          className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-medium hover:bg-muted disabled:opacity-50 transition-colors"
        >
          {portalLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Settings className="h-4 w-4" />
          )}
          Gérer mon abonnement
        </button>
        <p className="mt-2 text-xs text-center text-muted-foreground/50">
          Vous serez redirigé vers le portail de facturation Stripe.
        </p>
      </div>

      {/* All plans */}
      <div className="grid gap-6 lg:grid-cols-2">
        {planOrder.map((key, i) => {
          const plan = planDetails[key]
          return (
            <div
              key={key}
              className={`reveal relative rounded-xl border p-6 transition-shadow hover:shadow-lg ${
                key === currentPlan
                  ? 'border-primary bg-primary/5'
                  : 'border-border bg-card'
              }`}
              style={{ animationDelay: `${120 + i * 70}ms` }}
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
                  Messages illimités
                </li>
                <li className="flex items-center gap-2">
                  <Check className="h-4 w-4 text-green-500" />
                  Appels vocaux : 0,20€/min
                </li>
                <li className="flex items-center gap-2">
                  <Check className="h-4 w-4 text-green-500" />
                  Polyglotte (toutes langues)
                </li>
              </ul>

              {key !== currentPlan && (
                <button
                  onClick={() => handleCheckout(key)}
                  disabled={loadingPlan !== null}
                  className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-medium hover:bg-muted disabled:opacity-50 transition-colors"
                >
                  {loadingPlan === key ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <ArrowUpDown className="h-4 w-4" />
                  )}
                  {planOrder.indexOf(key) > planOrder.indexOf(currentPlan)
                    ? 'Passer à'
                    : 'Revenir à'}{' '}
                  {plan.name}
                </button>
              )}

              {key === currentPlan && (
                <div className="mt-6 space-y-2">
                  <div className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary/10 px-4 py-2.5 text-sm font-medium text-primary">
                    <Check className="h-4 w-4" />
                    Plan actuel
                  </div>
                  {/* Permet de souscrire via Stripe Checkout même sur le plan actuel
                      (utile si aucun abonnement Stripe n'est encore actif). */}
                  <button
                    onClick={() => handleCheckout(key)}
                    disabled={loadingPlan !== null}
                    className="flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-medium hover:bg-muted disabled:opacity-50 transition-colors"
                  >
                    {loadingPlan === key ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <CreditCard className="h-4 w-4" />
                    )}
                    Souscrire à ce plan
                  </button>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
