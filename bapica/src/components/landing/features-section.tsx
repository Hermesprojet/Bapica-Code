import { Bot, Globe, Shield, Zap, Headphones, CreditCard, BarChart3, MessageCircle, Palette, TrendingUp } from "lucide-react"

const features = [
  {
    icon: Bot,
    title: "Jusqu'à 12 agents spécialisés",
    desc: "De la prospection à la comptabilité, chaque métier a son agent IA dédié.",
    gradient: "from-indigo-500 to-blue-500",
  },
  {
    icon: MessageCircle,
    title: "WhatsApp & Web",
    desc: "Discutez avec vos agents depuis WhatsApp, votre navigateur ou par téléphone.",
    gradient: "from-emerald-500 to-green-500",
  },
  {
    icon: Globe,
    title: "Polyglotte",
    desc: "Détection automatique de la langue. Parlez-lui dans votre langue, il vous répond dans la même.",
    gradient: "from-indigo-500 to-blue-500",
  },
  {
    icon: Headphones,
    title: "Voix & téléphone",
    desc: "Agents vocaux avec Vapi et ElevenLabs. Réception et appels sortants.",
    gradient: "from-rose-500 to-pink-500",
  },
  {
    icon: Zap,
    title: "Automatisation n8n",
    desc: "Workflows puissants : prospectez, relancez, publiez automatiquement.",
    gradient: "from-amber-500 to-orange-500",
  },
  {
    icon: BarChart3,
    title: "Analytics intégré",
    desc: "Suivez vos performances, conversions et tendances en temps réel.",
    gradient: "from-teal-500 to-emerald-500",
  },
]

export function FeaturesSection() {
  return (
    <section id="features" className="relative border-t border-border py-20 md:py-28 overflow-hidden">
      <div className="absolute inset-0 bg-grid opacity-50" />
      <div className="container mx-auto px-4 relative">
        <div className="mx-auto mb-4 max-w-2xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary mb-6">
            Fonctionnalités
          </div>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Tout ce dont vous avez besoin,{" "}
            <span className="gradient-text">rien que l&apos;essentiel</span>
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Une plateforme complète pour propulser votre PME à l&apos;ère de l&apos;IA.
          </p>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 mt-12">
          {features.map((feature, index) => (
            <div
              key={feature.title}
              className="group relative rounded-xl border border-border bg-card p-6 transition-all duration-300 hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5 hover:-translate-y-1"
            >
              <div className="relative z-10">
                <div className={`mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-gradient-to-br ${feature.gradient} text-white shadow-lg transition-transform duration-300 group-hover:scale-110 group-hover:rotate-3`}>
                  <feature.icon className="h-6 w-6" />
                </div>
                <h3 className="mb-2 text-lg font-semibold">{feature.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{feature.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
