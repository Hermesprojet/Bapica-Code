import type { Metadata } from "next"
import Link from "next/link"
import { ArrowRight } from "lucide-react"
import { PublicPage } from "@/components/pages/public-page"
import { FAQSection } from "@/components/landing/faq-section"
import { getFAQSchema, JsonLdScript } from "@/lib/jsonld"

export const metadata: Metadata = {
  title: "FAQ — Questions fréquentes sur nos agents IA",
  description:
    "Toutes les réponses à vos questions sur Bapica : fonctionnement des agents IA, essai gratuit 15 jours, tarifs (49€ et 79€/mois), sécurité RGPD, langues supportées et plus.",
  keywords: [
    "FAQ Bapica",
    "questions agents IA",
    "tarifs Bapica",
    "essai gratuit IA",
    "sécurité données IA",
    "fonctionnement Bapica",
  ],
  alternates: {
    canonical: "https://bapica.com/faq",
  },
  openGraph: {
    title: "FAQ — Toutes vos questions sur Bapica et ses agents IA",
    description:
      "Fonctionnement, essai gratuit, tarifs, sécurité, langues : retrouvez toutes les réponses à vos questions sur la plateforme Bapica.",
  },
}

export default function FAQPage() {
  return (
    <PublicPage>
      {/* JSON-LD FAQ structured data for Google rich results */}
      <JsonLdScript data={getFAQSchema() as unknown as Record<string, unknown>} />

      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-grid opacity-40" />
        <div className="absolute left-1/2 top-[-30%] h-[380px] w-[600px] -translate-x-1/2 rounded-full bg-primary/10 blur-[130px]" />
        <div className="container relative mx-auto max-w-2xl px-4 pt-20 text-center md:pt-24">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-sm text-muted-foreground">
            Foire aux questions
          </div>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Vous avez des <span className="gradient-text">questions</span>&nbsp;?
          </h1>
          <p className="mx-auto mt-4 max-w-md text-lg text-muted-foreground">
            Retrouvez les réponses aux questions les plus fréquentes sur Bapica.
          </p>
        </div>
      </section>

      <FAQSection />

      <section className="border-t border-border py-16 md:py-20">
        <div className="container mx-auto max-w-2xl px-4 text-center">
          <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
            Vous ne trouvez pas votre réponse&nbsp;?
          </h2>
          <p className="mt-3 text-muted-foreground">
            Notre équipe est là pour vous aider. Contactez-nous, nous répondons
            rapidement.
          </p>
          <div className="mt-8">
            <Link
              href="/contact"
              className="group inline-flex h-12 items-center justify-center rounded-lg bg-primary px-8 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/25 transition-all hover:scale-105"
            >
              Nous contacter
              <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Link>
          </div>
        </div>
      </section>
    </PublicPage>
  )
}
