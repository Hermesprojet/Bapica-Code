import Link from "next/link"

export function CTASection() {
  return (
    <section className="border-t border-border py-20 md:py-28">
      <div className="container mx-auto px-4">
        <div className="relative overflow-hidden rounded-2xl gradient-hero px-8 py-16 text-center text-white">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(255,255,255,0.1),transparent_50%)]" />
          <div className="relative">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Prêt à propulser votre entreprise ?
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-lg text-white/80">
              Rejoignez les PME qui automatisent leur croissance avec nos agents IA.
            </p>
            <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
              <Link
                href="/signup"
                className="inline-flex h-12 items-center justify-center rounded-lg bg-white px-8 text-sm font-medium text-primary shadow-lg hover:bg-white/90 transition-all hover:scale-105"
              >
                Essai gratuit
              </Link>
              <Link
                href="#demo"
                className="inline-flex h-12 items-center justify-center rounded-lg border border-white/30 px-8 text-sm font-medium text-white hover:bg-white/10 transition-colors"
              >
                Parler à un conseiller
              </Link>
            </div>
            <p className="mt-6 text-sm text-white/60">
              Sans engagement • Configuration en 5 minutes • Résiliation à tout moment
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
