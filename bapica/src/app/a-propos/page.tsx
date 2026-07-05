import type { Metadata } from "next"
import Link from "next/link"
import { Target, Heart, Sparkles, Users, ArrowRight } from "lucide-react"
import { PublicPage } from "@/components/pages/public-page"

export const metadata: Metadata = {
  title: "À propos — L'équipe derrière les agents IA Bapica",
  description:
    "Bapica démocratise l'intelligence artificielle pour les PME et indépendants avec une équipe complète d'agents IA. Découvrez notre mission, nos valeurs et notre vision.",
  keywords: [
    "à propos Bapica",
    "équipe Bapica",
    "mission IA",
    "agents IA France",
    "startup IA française",
    "PME intelligence artificielle",
  ],
  alternates: {
    canonical: "https://bapica.com/a-propos",
  },
  openGraph: {
    title: "À propos de Bapica — Notre mission : démocratiser l'IA pour les PME",
    description:
      "Nous créons des agents IA spécialisés pour que chaque PME et indépendant puisse bénéficier de l'intelligence artificielle, sans compétences techniques.",
  },
}

const values = [
  {
    icon: Target,
    title: "Simplicité",
    desc: "Une IA puissante ne devrait pas exiger de compétences techniques. Nos agents sont prêts à l'emploi, sans configuration complexe.",
    gradient: "from-violet-500 to-purple-500",
  },
  {
    icon: Heart,
    title: "Proximité",
    desc: "Nous concevons Bapica pour les indépendants et les petites équipes, avec un accompagnement humain et une écoute réelle.",
    gradient: "from-rose-500 to-pink-500",
  },
  {
    icon: Sparkles,
    title: "Utilité concrète",
    desc: "Chaque agent répond à un vrai besoin métier : trouver des clients, répondre au support, créer du contenu, gérer l'administratif.",
    gradient: "from-amber-500 to-orange-500",
  },
  {
    icon: Users,
    title: "Confiance",
    desc: "Sécurité, transparence et conformité RGPD au cœur de nos choix. Vos données restent les vôtres.",
    gradient: "from-teal-500 to-emerald-500",
  },
]

export default function AProposPage() {
  return (
    <PublicPage>
      {/* Hero */}
      <section className="relative overflow-hidden border-b border-border">
        <div className="absolute inset-0 bg-grid opacity-40" />
        <div className="absolute left-1/2 top-[-30%] h-[420px] w-[640px] -translate-x-1/2 rounded-full bg-primary/10 blur-[130px]" />
        <div className="container relative mx-auto max-w-3xl px-4 py-20 text-center md:py-28">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-sm text-muted-foreground">
            À propos de Bapica
          </div>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl">
            L&apos;IA au service des{" "}
            <span className="gradient-text">petites entreprises</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
            Bapica est née d&apos;une conviction simple : les PME et les
            indépendants méritent les mêmes outils d&apos;intelligence
            artificielle que les grands groupes, sans la complexité ni le budget
            associés.
          </p>
        </div>
      </section>

      {/* Mission */}
      <section className="container mx-auto max-w-3xl px-4 py-16 md:py-20">
        <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
          Notre mission
        </h2>
        <div className="mt-4 space-y-4 text-muted-foreground leading-relaxed">
          <p>
            Trop d&apos;entrepreneurs passent leurs journées noyés dans des
            tâches répétitives : prospecter, répondre aux clients, rédiger du
            contenu, relancer des factures. Autant de temps qui n&apos;est pas
            consacré à leur cœur de métier.
          </p>
          <p>
            Nous avons imaginé Bapica comme une véritable équipe d&apos;agents
            IA, chacun spécialisé dans un domaine, accessible depuis une seule
            plateforme. L&apos;objectif : rendre l&apos;IA aussi simple à
            utiliser qu&apos;une conversation, pour que chaque professionnel
            puisse déléguer et se concentrer sur l&apos;essentiel.
          </p>
        </div>
      </section>

      {/* Valeurs */}
      <section className="border-t border-border py-16 md:py-20">
        <div className="container mx-auto max-w-4xl px-4">
          <div className="mb-12 text-center">
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
              Nos valeurs
            </h2>
            <p className="mt-3 text-muted-foreground">
              Ce qui guide chacune de nos décisions.
            </p>
          </div>
          <div className="grid gap-6 sm:grid-cols-2">
            {values.map((v) => (
              <div
                key={v.title}
                className="rounded-xl border border-border bg-card p-6 transition-all hover:border-primary/30 hover:-translate-y-1"
              >
                <div
                  className={`mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-gradient-to-br ${v.gradient} text-white shadow-lg`}
                >
                  <v.icon className="h-6 w-6" />
                </div>
                <h3 className="mb-2 text-lg font-semibold">{v.title}</h3>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {v.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-border py-16 md:py-20">
        <div className="container mx-auto max-w-2xl px-4 text-center">
          <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
            Envie d&apos;en savoir plus&nbsp;?
          </h2>
          <p className="mt-3 text-muted-foreground">
            Testez gratuitement pendant 15 jours ou écrivez-nous, nous serons
            ravis d&apos;échanger.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link
              href="/signup"
              className="group inline-flex h-12 items-center justify-center rounded-lg bg-primary px-8 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/25 transition-all hover:scale-105"
            >
              Commencer gratuitement
              <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Link>
            <Link
              href="/contact"
              className="inline-flex h-12 items-center justify-center rounded-lg border border-border bg-background/50 px-8 text-sm font-medium transition-all hover:border-primary/50 hover:bg-muted"
            >
              Nous contacter
            </Link>
          </div>
        </div>
      </section>
    </PublicPage>
  )
}
