import Link from "next/link"

export function HeroSection() {
  return (
    <section className="relative overflow-hidden pt-32 pb-20 md:pt-40 md:pb-28">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,hsl(var(--primary)/0.15),transparent_50%)]" />
      <div className="container mx-auto px-4 text-center relative">
        <div className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-sm">
          <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-muted-foreground">12 agents IA prêts à l&apos;emploi</span>
        </div>
        <h1 className="mx-auto max-w-4xl text-4xl font-bold tracking-tight sm:text-5xl md:text-6xl">
          Propulsez votre PME avec{" "}
          <span className="gradient-text">12 agents IA spécialisés</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
          Prospection, support client, contenu, voix, recrutement, comptabilité...
          Une équipe complète d&apos;agents IA pour développer votre activité, 24h/24 et 7j/7.
        </p>
        <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
          <Link
            href="/signup"
            className="inline-flex h-12 items-center justify-center rounded-lg bg-primary px-8 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/25 hover:bg-primary/90 transition-all hover:scale-105"
          >
            Commencer gratuitement
          </Link>
          <Link
            href="#diagnostic"
            className="inline-flex h-12 items-center justify-center rounded-lg border border-border bg-background px-8 text-sm font-medium hover:bg-muted transition-colors"
          >
            Diagnostic gratuit
          </Link>
        </div>
        <div className="mt-12 flex items-center justify-center gap-8 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <span className="text-green-500">✓</span> Sans engagement
          </div>
          <div className="flex items-center gap-2">
            <span className="text-green-500">✓</span> Configuration 5 min
          </div>
          <div className="flex items-center gap-2">
            <span className="text-green-500">✓</span> Multilingue FR/EN/AR
          </div>
        </div>
      </div>
    </section>
  )
}
