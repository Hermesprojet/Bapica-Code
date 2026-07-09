import { Bot, Globe, Shield, Zap, Headphones, CreditCard, BarChart3 } from "lucide-react"

const features = [
  {
    number: "01",
    icon: Bot,
    title: "13 agents spécialisés",
    desc: "De la prospection à la comptabilité, chaque métier a son agent IA dédié qui comprend votre contexte.",
  },
  {
    number: "02",
    icon: Headphones,
    title: "Voix & téléphone",
    desc: "Agents vocaux qui répondent à vos clients, filtrent les appels et planifient vos rendez-vous.",
  },
  {
    number: "03",
    icon: Globe,
    title: "Toutes les langues",
    desc: "Détection automatique de la langue. Parlez-lui dans votre langue, il vous répond dans la même.",
  },
  {
    number: "04",
    icon: BarChart3,
    title: "Analytics intégré",
    desc: "Suivez vos performances, conversions et tendances en temps réel depuis votre tableau de bord.",
  },
  {
    number: "05",
    icon: Zap,
    title: "Automatisation n8n",
    desc: "Workflows puissants : prospectez, relancez, publiez automatiquement sans intervention humaine.",
  },
  {
    number: "06",
    icon: Shield,
    title: "Sécurité & souveraineté",
    desc: "Hébergement en Europe, chiffrement, conformité RGPD incluse. Vos données vous appartiennent.",
  },
]

export function FeaturesSection() {
  return (
    <section id="features" className="py-16 md:py-24 section-tinted-full">
      <div className="container mx-auto max-w-6xl px-4">
        <div className="mb-12">
          <p className="section-label">UNE PLATEFORME COMPLÈTE</p>
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
            Tout ce dont votre entreprise a besoin,<br />
            <span className="gradient-text">rien de superflu</span>
          </h2>
        </div>

        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <div key={f.number} className="numbered-item group">
              <span className="number-badge">{f.number}</span>
              <div>
                <div className="flex items-center gap-3 mb-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/5 text-primary">
                    <f.icon className="h-5 w-5" />
                  </div>
                  <h3 className="font-semibold">{f.title}</h3>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed">{f.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
