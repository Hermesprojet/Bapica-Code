import { TrendingUp, Clock, Users, Zap } from "lucide-react"

export function ROIStats() {
  return (
    <section className="border-t border-border bg-muted/20 py-10 sm:py-12">
      <div className="container mx-auto max-w-5xl px-4">
        <div className="text-center mb-10">
          <span className="section-label">RÉSULTATS MESURABLES</span>
          <h2 className="mt-2 text-2xl sm:text-3xl font-bold">
            Vos concurrents utilisent déjà l&apos;IA.{" "}
            <span className="gradient-text">Voici ce que vous ratez.</span>
          </h2>
        </div>

        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {[
            {
              icon: TrendingUp,
              value: "3×",
              label: "plus de leads qualifiés",
              detail: "vs prospection manuelle",
              color: "text-green-500",
            },
            {
              icon: Clock,
              value: "32h",
              label: "économisées par semaine",
              detail: "sur les tâches répétitives",
              color: "text-blue-500",
            },
            {
              icon: Zap,
              value: "80%",
              label: "de réduction des coûts",
              detail: "vs un employé équivalent",
              color: "text-amber-500",
            },
            {
              icon: Users,
              value: "55%",
              label: "de réponse en plus",
              detail: "sur vos relances commerciales",
              color: "text-purple-500",
            },
          ].map((stat, i) => (
            <div key={i} className="card-professional p-6 text-center group hover:border-primary/30 transition-colors">
              <stat.icon className={`h-8 w-8 ${stat.color} mx-auto mb-3`} />
              <div className={`text-4xl font-bold ${stat.color} mb-1`}>{stat.value}</div>
              <div className="text-sm font-semibold text-foreground">{stat.label}</div>
              <div className="text-xs text-muted-foreground/60 mt-1">{stat.detail}</div>
            </div>
          ))}
        </div>

        <p className="mt-8 text-center text-sm text-muted-foreground/60">
          ✦ Basé sur les résultats moyens de nos clients après 3 mois d&apos;utilisation
        </p>
      </div>
    </section>
  )
}
