import Link from "next/link"
import { ArrowRight, Play } from "lucide-react"

export function HeroSection() {
  return (
    <section className="relative overflow-hidden pt-20 sm:pt-24 pb-12 sm:pb-16 md:pt-36 md:pb-24 section-glow section-glow-tr">
      <div className="container mx-auto max-w-6xl px-4">
        <div className="grid lg:grid-cols-2 gap-8 md:gap-12 items-center">

          {/* Left column - Text */}
          <div className="animate-fade-in text-center lg:text-left">
            <h1 className="text-2xl sm:text-4xl md:text-5xl lg:text-6xl font-bold leading-[1.15] sm:leading-[1.1] tracking-tight text-foreground">
              Votre entreprise mérite<br />
              <em className="not-italic gradient-text">ses propres agents IA</em>
            </h1>
            <p className="mt-4 sm:mt-6 text-sm sm:text-lg text-muted-foreground leading-relaxed max-w-xl lg:mx-0 mx-auto">
              Bapica vous donne accès à une équipe d&apos;agents IA spécialisés qui comprennent votre métier et exécutent vos tâches 24h/24.
            </p>
            <p className="mt-3 sm:mt-4 text-xs sm:text-base text-muted-foreground/80 leading-relaxed max-w-xl lg:mx-0 mx-auto">
              Ne louez plus l&apos;intelligence. Construisez votre équipe IA, formée à vos méthodes et dédiée à votre entreprise.
            </p>

            <div className="mt-6 sm:mt-8 flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center lg:justify-start">
              <Link href="/signup" className="btn-primary group w-full sm:w-auto">
                Commencer gratuitement
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>
              <Link href="#agents" className="btn-outline w-full sm:w-auto">
                <Play className="h-4 w-4" />
                Découvrir les agents
              </Link>
            </div>

            <div className="mt-6 sm:mt-8 flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-3 sm:gap-6 text-xs sm:text-sm text-muted-foreground/60">
              <span className="flex items-center gap-1.5">★★★★★ <span className="text-foreground font-medium">4.9</span></span>
              <span>déjà <strong className="text-foreground font-semibold">+100</strong> entreprises</span>
            </div>
          </div>

          {/* Right column - Demo video */}
          <div className="animate-fade-in relative hidden lg:block">
            <div className="rounded-2xl border border-border overflow-hidden shadow-lg">
              <video
                src="/bapica-demo.mp4"
                poster="/opengraph-image"
                controls
                preload="metadata"
                className="w-full aspect-video"
                style={{ background: "#0a1628" }}
              >
                Votre navigateur ne supporte pas la lecture vidéo.
              </video>
            </div>
            <p className="mt-3 text-center text-xs text-muted-foreground/50">
              Vidéo de présentation · 1 min 18 s
            </p>
          </div>
        </div>
      </div>

      {/* Guarantee strip */}
      <div className="guarantee-strip mt-12 sm:mt-16 md:mt-24">
        <span><strong>Messagerie illimitée</strong></span>
        <span className="hidden sm:inline text-border">|</span>
        <span><strong>Appels 0,20€/min</strong></span>
        <span className="hidden sm:inline text-border">|</span>
        <span><strong>12 agents</strong> spécialisés</span>
        <span className="hidden sm:inline text-border">|</span>
        <span><strong>Hébergement</strong> Europe</span>
        <span className="hidden sm:inline text-border">|</span>
        <span><strong>RGPD</strong></span>
      </div>
    </section>
  )
}
