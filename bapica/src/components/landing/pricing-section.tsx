import Link from "next/link"
import { Check } from "lucide-react"

const plans = [
  {
    name: "Starter",
    price: "29",
    desc: "Pour indépendants et micro-entreprises",
    popular: false,
    features: [
      "3 agents IA au choix",
      "Support Client inclus",
      "Agent Général inclus",
      "1 000 messages/mois",
      "Chat web + email",
      "Multilingue FR/EN/AR",
    ],
  },
  {
    name: "Pro",
    price: "59",
    desc: "Pour PME en croissance",
    popular: true,
    features: [
      "Jusqu'à 7 agents IA",
      "Prospecteur Commercial",
      "Agent Téléphonique (Vapi)",
      "Agent Comptabilité",
      "5 000 messages/mois",
      "60 min d'appels vocaux/mois",
      "Workflows n8n inclus",
      "Support prioritaire",
    ],
  },
  {
    name: "Business",
    price: "99",
    desc: "Pour entreprises établies",
    popular: false,
    features: [
      "12 agents IA (tous inclus)",
      "Créateur Vidéo IA (HeyGen)",
      "Recruteur IA",
      "Analytics & Reporting",
      "Messages illimités",
      "300 min d'appels vocaux/mois",
      "API access",
      "Agent dédié + support 24/7",
    ],
  },
]

export function PricingSection() {
  return (
    <section id="pricing" className="border-t border-border py-20 md:py-28">
      <div className="container mx-auto px-4">
        <div className="mx-auto mb-16 max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Des tarifs <span className="gradient-text">transparents</span>
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Pas de frais cachés. Pas de contrat. Résiliez à tout moment.
          </p>
        </div>
        <div className="grid gap-8 lg:grid-cols-3">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`relative rounded-xl border ${
                plan.popular
                  ? "border-primary bg-primary/5 shadow-lg shadow-primary/10 scale-105"
                  : "border-border bg-card"
              } p-8 transition-all hover:shadow-xl`}
            >
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-primary px-4 py-1 text-xs font-semibold text-primary-foreground">
                  Le plus populaire
                </div>
              )}
              <h3 className="text-xl font-bold">{plan.name}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{plan.desc}</p>
              <div className="mt-6 flex items-baseline gap-1">
                <span className="text-4xl font-bold">{plan.price}€</span>
                <span className="text-muted-foreground">/mois</span>
              </div>
              <ul className="mt-8 space-y-3">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-3 text-sm">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-green-500" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
              <Link
                href="/signup"
                className={`mt-8 flex h-12 w-full items-center justify-center rounded-lg text-sm font-medium transition-all ${
                  plan.popular
                    ? "bg-primary text-primary-foreground shadow-lg shadow-primary/25 hover:bg-primary/90"
                    : "border border-border bg-background hover:bg-muted"
                }`}
              >
                Commencer avec {plan.name}
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
