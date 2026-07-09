import Link from "next/link"
import { Check, ArrowRight, Sparkles } from "lucide-react"

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
    promoCode: "BAPICA10",
    promoLabel: "-10% avec le code",
  },
  {
    name: "Pro",
    price: "79",
    oldPrice: "99",
    desc: "Pour PME qui veulent accélérer leur croissance",
    popular: true,
    features: [
      "13 agents IA (tous inclus)",
      "Agent Téléphonique IA",
      "Créateur Vidéo IA (HeyGen)",
      "Agent Juridique & Comptable",
      "Recruteur IA",
      "Analytics & Reporting",
      "Messages illimités",
    ],
    extra: "Appels vocaux : 0,20€/min",
    promoCode: "BAPICA10",
    promoLabel: "-10% avec le code",
  },
]

export function PricingSection() {
  return (
    <section id="pricing" className="py-16 md:py-24">
      {/* 🔥 Banner promo - like Limova */}
      <div className="bg-foreground text-background py-3 text-center text-sm font-medium px-4">
        <Sparkles className="inline h-4 w-4 mr-2" />
        Offre lancement : <code className="bg-background/20 px-2 py-0.5 rounded font-mono text-xs">BAPICA10</code> = -10% sur les offres mensuelles · <code className="bg-background/20 px-2 py-0.5 rounded font-mono text-xs">BAPICA25</code> = -25% sur les offres annuelles
      </div>

      <div className="container mx-auto max-w-6xl px-4 mt-16">
        <div className="mb-12">
          <p className="section-label">TARIFS</p>
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
            Des tarifs <span className="gradient-text">transparents</span>
          </h2>
          <p className="mt-4 text-muted-foreground max-w-xl">
            Pas de frais cachés. Pas de contrat. Résiliez à tout moment.
          </p>
        </div>

        <div className="grid gap-8 lg:grid-cols-2 max-w-4xl">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`relative rounded-xl border p-8 transition-all ${
                plan.popular
                  ? "border-foreground/20 bg-foreground/[0.02] shadow-sm"
                  : "border-border bg-card"
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-3 left-6 rounded-full bg-foreground px-4 py-1 text-xs font-semibold text-background">
                  Le plus populaire
                </div>
              )}

              <h3 className="text-lg font-bold">{plan.name}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{plan.desc}</p>

              <div className="mt-6 flex items-baseline gap-2">
                <span className="text-sm text-muted-foreground/50 line-through">{plan.oldPrice}€</span>
                <span className="text-4xl font-bold tracking-tight">{plan.price}€</span>
                <span className="text-muted-foreground">HT/mois</span>
              </div>

              {/* Promo code - visible like Limova */}
              <div className="mt-3 flex items-center gap-2 rounded-lg bg-green-500/10 border border-green-500/20 px-3 py-2">
                <span className="text-[11px] font-semibold uppercase text-green-600 tracking-wide">Code promo</span>
                <code className="font-mono text-sm font-bold text-green-600">{plan.promoCode}</code>
                <span className="text-[11px] text-green-600/70">{plan.promoLabel}</span>
              </div>

              <p className="mt-3 text-xs text-muted-foreground/70 bg-muted/50 rounded-lg px-3 py-2">
                {plan.extra}
              </p>

              <ul className="mt-6 space-y-3">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-3 text-sm">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-green-500" />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>

              <Link
                href="/signup"
                className={`mt-8 flex h-12 w-full items-center justify-center gap-2 rounded-lg text-sm font-medium transition-all group ${
                  plan.popular
                    ? "bg-foreground text-background hover:bg-foreground/90"
                    : "border border-border bg-card hover:bg-muted"
                }`}
              >
                Commencer avec {plan.name}
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
