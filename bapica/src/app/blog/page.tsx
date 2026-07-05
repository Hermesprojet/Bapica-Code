import type { Metadata } from "next"
import Link from "next/link"
import { Newspaper, ArrowRight } from "lucide-react"
import { PublicPage } from "@/components/pages/public-page"

export const metadata: Metadata = {
  title: "Blog IA & Productivité — Conseils pour PME et indépendants",
  description:
    "Le blog de Bapica : conseils IA, productivité et automatisation pour PME et indépendants. Articles sur les agents IA, la prospection, le support client et plus.",
  keywords: [
    "blog IA",
    "conseils productivité",
    "automatisation PME",
    "agents IA",
    "intelligence artificielle entreprise",
    "blog Bapica",
  ],
  alternates: {
    canonical: "https://bapica.com/blog",
  },
  openGraph: {
    title: "Blog Bapica — IA, productivité et automatisation pour les PME",
    description:
      "Découvrez nos articles sur l'intelligence artificielle, les agents IA et l'automatisation pour les PME et indépendants.",
  },
}

export default function BlogPage() {
  return (
    <PublicPage>
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-grid opacity-40" />
        <div className="absolute left-1/2 top-[-30%] h-[420px] w-[640px] -translate-x-1/2 rounded-full bg-primary/10 blur-[130px]" />
        <div className="container relative mx-auto max-w-2xl px-4 py-24 text-center md:py-32">
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-blue-500 text-white shadow-lg shadow-primary/20">
            <Newspaper className="h-8 w-8" />
          </div>
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-sm text-muted-foreground">
            Blog en construction
          </div>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Notre <span className="gradient-text">blog</span> arrive bientôt
          </h1>
          <p className="mx-auto mt-4 max-w-md text-lg text-muted-foreground">
            Nous préparons des articles sur l&apos;IA, la productivité et
            l&apos;automatisation pour les PME et indépendants. Revenez très
            vite&nbsp;!
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
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
