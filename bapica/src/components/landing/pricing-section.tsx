import Link from "next/link"

const plans = [
  {
    name: "Essentiel",
    price: "49",
    oldPrice: "69",
    desc: "Pour indépendants et TPE qui veulent automatiser leur quotidien",
    popular: false,
    features: [
      "8 agents IA spécialisés",
      "Marketing Automation (posts, visuels)",
      "SEO automatisé (articles + audit)",
      "Prospection LinkedIn",
      "Génération de documents",
      "Accès API inclus",
      "Messages illimités",
    ],
    extra: "Appels vocaux : 0,20€/min",
    code: "BAPICA10",
  },
  {
    name: "Pro",
    price: "79",
    oldPrice: "99",
    desc: "Pour PME qui veulent accélérer leur croissance",
    popular: true,
    features: [
      "12 agents IA (tous inclus)",
      "Agent Téléphonique IA (Tom)",
      "Créateur Vidéo IA (HeyGen)",
      "Agent Juridique & Comptable",
      "Recruteur IA",
      "Analytics & Reporting",
      "Messages illimités",
    ],
    extra: "Appels vocaux : 0,20€/min",
    code: "BAPICA10",
  },
]

export function PricingSection() {
  return (
    <section id="pricing" className="relative border-t border-border py-20 md:py-28 overflow-hidden">
      <div className="absolute inset-0 bg-grid opacity-30" />
      
      <div className="container mx-auto px-4 relative">
        <div className="mx-auto mb-4 max-w-2xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary mb-6">
            💰 Tarifs
          </div>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Des tarifs <span className="gradient-text">transparents</span>
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            5x plus productif, 10x moins cher. Pas de frais cachés.
          </p>
        </div>

        <div className="mx-auto mb-10 flex items-center justify-center gap-4 text-sm flex-wrap">
          <div className="rounded-full bg-primary/10 px-4 py-1.5 text-primary font-medium backdrop-blur-sm">
            🔥 OFFRE LANCEMENT : -10% avec le code <span className="font-bold">BAPICA10</span>
          </div>
          <div className="rounded-full bg-emerald-500/10 px-4 py-1.5 text-emerald-400 font-medium backdrop-blur-sm border border-emerald-500/20">
            🎁 15 jours d&apos;essai gratuit — sans carte bancaire
          </div>
        </div>

        <div className="grid gap-8 lg:grid-cols-2 max-w-4xl mx-auto">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`relative rounded-xl border ${
                plan.popular
                  ? "border-primary bg-primary/5 shadow-lg shadow-primary/10 scale-105"
                  : "border-border bg-card"
              } p-8 transition-all duration-300 hover:shadow-xl hover:-translate-y-1`}
            >
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-gradient-to-r from-primary to-purple-500 px-4 py-1 text-xs font-semibold text-primary-foreground shadow-lg">
                  Le plus populaire
                </div>
              )}
              <h3 className="text-xl font-bold">{plan.name}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{plan.desc}</p>
              <div className="mt-6 flex items-baseline gap-2">
                <span className="text-sm text-muted-foreground line-through">{plan.oldPrice}€</span>
                <span className="text-4xl font-bold">{plan.price}€</span>
                <span className="text-muted-foreground">/mois</span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Code <span className="font-mono font-medium text-primary">{plan.code}</span> : -10%
              </p>
              <div className="mt-4 rounded-lg bg-muted/50 px-3 py-2 text-xs text-muted-foreground border border-border">
                {plan.extra}
              </div>
              <ul className="mt-6 space-y-3">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-3 text-sm">
                    <svg className="mt-0.5 h-4 w-4 shrink-0 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
              <Link
                href="/signup"
                className={`mt-8 flex h-12 w-full items-center justify-center rounded-lg text-sm font-medium transition-all ${
                  plan.popular
                    ? "bg-gradient-to-r from-primary to-purple-500 text-primary-foreground shadow-lg shadow-primary/25 hover:shadow-primary/40 hover:scale-[1.02]"
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
