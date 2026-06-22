import { Bot, Globe, Shield, Zap, Headphones, CreditCard } from "lucide-react"

const features = [
  {
    icon: Bot,
    title: "11 agents spécialisés",
    desc: "De la prospection à la comptabilité, chaque métier a son agent dédié.",
  },
  {
    icon: Globe,
    title: "Trilingue FR/EN/AR",
    desc: "Vos agents parlent français, anglais et arabe — détection automatique.",
  },
  {
    icon: Shield,
    title: "Sécurité & RGPD",
    desc: "Hébergement sécurisé, chiffrement, conformité RGPD incluse.",
  },
  {
    icon: Zap,
    title: "Automatisation n8n",
    desc: "Workflows puissants pour prospecter, relancer, publier automatiquement.",
  },
  {
    icon: Headphones,
    title: "Voix & téléphone",
    desc: "Agents vocaux avec Vapi et ElevenLabs — naturels et professionnels.",
  },
  {
    icon: CreditCard,
    title: "Sans engagement",
    desc: "Arrêtez quand vous voulez. Pas de contrat, pas de surprise.",
  },
]

export function FeaturesSection() {
  return (
    <section id="features" className="border-t border-border py-20 md:py-28">
      <div className="container mx-auto px-4">
        <div className="mx-auto mb-16 max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Tout ce dont vous avez besoin
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Une plateforme complète pour propulser votre PME à l&apos;ère de l&apos;IA.
          </p>
        </div>
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <div key={feature.title} className="group rounded-xl border border-border bg-card p-6 hover:border-primary/50 transition-all">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary group-hover:scale-110 transition-transform">
                <feature.icon className="h-6 w-6" />
              </div>
              <h3 className="mb-2 text-lg font-semibold">{feature.title}</h3>
              <p className="text-sm text-muted-foreground">{feature.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
