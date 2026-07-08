import { Brain, Target, LineChart, Users, Sparkles } from "lucide-react"

const steps = [
  {
    icon: Brain,
    title: "Analyse de votre business",
    desc: "En 5 minutes, Bapica analyse votre secteur, votre taille, vos objectifs et vos outils. Pas de configuration — l'IA comprend automatiquement votre contexte.",
    color: "from-primary to-blue-600",
  },
  {
    icon: Target,
    title: "Diagnostic personnalisé",
    desc: "Score de maturité, benchmarks sectoriels, risques identifiés, opportunités de croissance. Un rapport complet généré automatiquement.",
    color: "from-purple-600 to-pink-600",
  },
  {
    icon: Users,
    title: "Équipe d'agents sur mesure",
    desc: "Les agents IA les plus pertinents sont recommandés automatiquement. Chacun est spécialisé dans un domaine clé de votre activité.",
    color: "from-amber-600 to-orange-600",
  },
  {
    icon: LineChart,
    title: "ROI en temps réel",
    desc: "Heures économisées, revenus potentiels, accélération de croissance. Tout est calculé et mis à jour en fonction de votre progression.",
    color: "from-green-600 to-emerald-600",
  },
  {
    icon: Sparkles,
    title: "Amélioration continue",
    desc: "Plus vous utilisez Bapica, plus la plateforme affine ses recommandations. Votre analyste IA personnel est disponible 24/7.",
    color: "from-violet-600 to-purple-600",
  },
]

export function IntelligenceSection() {
  return (
    <section className="border-t border-border py-16 sm:py-20 md:py-28 bg-muted/30">
      <div className="container mx-auto max-w-6xl px-4">
        <div className="text-center mb-12 md:mb-16">
          <span className="section-label">INTELLIGENCE ADAPTATIVE</span>
          <h2 className="mt-3 text-2xl sm:text-3xl md:text-4xl font-bold">
            Une IA qui{" "}
            <span className="bg-gradient-to-r from-primary to-purple-600 bg-clip-text text-transparent">
              apprend de votre business
            </span>
          </h2>
          <p className="mt-4 text-muted-foreground max-w-2xl mx-auto text-base sm:text-lg">
            Contrairement aux chatbots génériques, Bapica analyse votre entreprise en profondeur 
            et s&apos;adapte continuellement. Chaque recommandation est basée sur votre réalité, 
            pas sur des généralités.
          </p>
        </div>

        {/* Steps */}
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-5">
          {steps.map((step, i) => (
            <div key={i} className="relative group">
              {/* Connection line */}
              {i < steps.length - 1 && (
                <div className="hidden lg:block absolute top-8 left-[calc(50%+2rem)] w-[calc(100%-2rem)] h-0.5">
                  <div className="h-full bg-gradient-to-r from-border/50 to-border/10" />
                </div>
              )}
              
              <div className="text-center">
                <div className={`inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br ${step.color} text-white shadow-lg mb-4 group-hover:scale-110 transition-transform`}>
                  <step.icon className="h-7 w-7" />
                </div>
                <h3 className="font-semibold text-sm mb-2">{step.title}</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">{step.desc}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Trust note */}
        <div className="mt-12 text-center">
          <p className="text-sm text-muted-foreground/60">
            ✦ L&apos;analyse initiale prend <strong className="text-foreground">moins de 5 minutes</strong> · 
            Aucune configuration manuelle · 
            Mise à jour automatique en continu
          </p>
        </div>
      </div>
    </section>
  )
}
