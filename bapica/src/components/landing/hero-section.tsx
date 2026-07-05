import Link from "next/link"
import { ArrowRight, Play } from "lucide-react"

export function HeroSection() {
  return (
    <section className="relative overflow-hidden pt-24 pb-16 md:pt-36 md:pb-24">
      <div className="container mx-auto max-w-6xl px-4">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          
          {/* Left column - Text */}
          <div className="animate-fade-in">
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold leading-[1.1] tracking-tight text-foreground">
              Votre entreprise mérite<br />
              <em className="not-italic gradient-text">ses propres agents IA</em>
            </h1>
            <p className="mt-6 text-lg text-muted-foreground leading-relaxed max-w-xl">
              Bapica vous donne accès à une équipe d&apos;agents IA spécialisés qui comprennent votre métier et exécutent vos tâches 24h/24.
            </p>
            <p className="mt-4 text-base text-muted-foreground/80 leading-relaxed max-w-xl">
              Ne louez plus l&apos;intelligence. Construisez votre équipe IA, formée à vos méthodes et dédiée à votre entreprise.
            </p>

            <div className="mt-8 flex flex-col sm:flex-row gap-4">
              <Link href="/signup" className="btn-primary group">
                Commencer gratuitement
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>
              <Link href="#agents" className="btn-outline">
                <Play className="h-4 w-4" />
                Découvrir les agents
              </Link>
            </div>

            <div className="mt-8 flex items-center gap-6 text-sm text-muted-foreground/60">
              <span className="flex items-center gap-1.5">★★★★★ <span className="text-foreground font-medium">4.9</span></span>
              <span className="flex items-center gap-1">déjà adoptée par <strong className="text-foreground font-semibold">+100</strong> entreprises</span>
            </div>
          </div>

          {/* Right column - Visual placeholder */}
          <div className="animate-fade-in relative hidden lg:block">
            <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
              <div className="flex items-center gap-2 mb-4">
                <div className="flex gap-1.5">
                  <span className="h-3 w-3 rounded-full bg-red-400" />
                  <span className="h-3 w-3 rounded-full bg-yellow-400" />
                  <span className="h-3 w-3 rounded-full bg-green-400" />
                </div>
                <span className="text-xs text-muted-foreground/50">terminal · bapica</span>
              </div>
              <div className="space-y-2 font-mono text-sm text-muted-foreground">
                <p><span className="text-foreground">$</span> bapica assist</p>
                <p className="text-green-600">✓ Agent Léo connecté</p>
                <p className="text-green-600">✓ 12 agents disponibles</p>
                <p><span className="text-foreground">$</span> bapica automate --task factures</p>
                <p className="text-blue-600">→ L&apos;agent Comptable traite vos factures...</p>
                <p className="text-blue-600">→ 23 factures traitées en 2.4s</p>
                <p className="text-blue-600">→ Rapport envoyé par email</p>
                <p className="animate-pulse"><span className="text-foreground">$</span> _</p>
              </div>
            </div>
            {/* Decorative dots */}
            <div className="absolute -bottom-4 -right-4 w-24 h-24 rounded-full bg-gradient-to-br from-primary/5 to-transparent blur-xl" />
          </div>

        </div>
      </div>

      {/* Guarantee strip */}
      <div className="guarantee-strip mt-16 md:mt-24">
        <span><strong>Messagerie illimitée</strong></span>
        <span className="hidden sm:inline text-border">|</span>
        <span><strong>Appels 0,20€/min</strong></span>
        <span className="hidden sm:inline text-border">|</span>
        <span><strong>12 agents</strong> spécialisés</span>
        <span className="hidden sm:inline text-border">|</span>
        <span><strong>Hébergement</strong> en Europe</span>
        <span className="hidden sm:inline text-border">|</span>
        <span><strong>Conforme</strong> RGPD</span>
      </div>
    </section>
  )
}
