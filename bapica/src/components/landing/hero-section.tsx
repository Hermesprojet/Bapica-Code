import Link from "next/link"
import { ArrowRight, Brain, Sparkles, Zap } from "lucide-react"

export function HeroSection() {
  return (
    <section className="relative overflow-hidden pt-20 sm:pt-24 pb-12 sm:pb-16 md:pt-36 md:pb-24">
      <div className="container mx-auto max-w-6xl px-4">
        <div className="grid gap-10 md:grid-cols-2 md:items-center">
          {/* Texte */}
          <div className="text-center md:text-left">
            {/* Badge */}
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5">
              <Brain className="h-4 w-4 text-primary" />
              <span className="text-xs font-semibold tracking-[0.15em] uppercase text-primary">
                Intelligence Adaptative
              </span>
            </div>

            <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold leading-tight tracking-tight">
              Des agents IA qui{" "}
              <span className="block bg-gradient-to-r from-primary via-purple-600 to-blue-600 bg-clip-text text-transparent">
                comprennent votre business
              </span>
            </h1>

            <p className="mt-4 md:mt-6 text-base sm:text-lg text-muted-foreground leading-relaxed max-w-xl">
              Bapica n&apos;est pas un simple chatbot. C&apos;est une plateforme qui{" "}
              <strong className="text-foreground">analyse votre entreprise en profondeur</strong>,
              comprend vos enjeux, et déploie une équipe d&apos;agents IA
              <strong className="text-foreground"> sur mesure</strong> pour votre activité.
            </p>

            <p className="mt-3 text-sm text-muted-foreground/70">
              Chaque agent s&apos;adapte à votre secteur, votre taille, vos objectifs. 
              Pas de configuration compliquée — l&apos;intelligence est automatique.
            </p>

            <div className="mt-6 md:mt-8 flex flex-col sm:flex-row gap-3 justify-center md:justify-start">
              <Link
                href="/signup"
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-foreground px-6 py-3 text-sm font-semibold text-background hover:bg-foreground/90 transition-colors"
              >
                Commencer gratuitement
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="#features"
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-border px-6 py-3 text-sm font-medium hover:bg-muted transition-colors"
              >
                Comment ça marche
              </Link>
            </div>

            {/* Stats */}
            <div className="mt-8 flex flex-wrap items-center gap-4 sm:gap-6 text-sm justify-center md:justify-start">
              <div className="flex items-center gap-2">
                <span className="text-amber-500">★★★★★</span>
                <span className="text-muted-foreground">4.9 · +100 entreprises</span>
              </div>
              <span className="text-muted-foreground/40 hidden sm:inline">|</span>
              <span className="text-muted-foreground">
                Analyse en <strong className="text-foreground">1 minute</strong>
              </span>
            </div>
          </div>

          {/* Visuel */}
          <div className="relative hidden md:block">
            <div className="relative rounded-xl border border-border/50 bg-gradient-to-br from-muted/80 to-card p-6 shadow-2xl">
              {/* Terminal-like analysis display */}
              <div className="flex items-center gap-2 mb-4">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-red-400/60" />
                  <div className="w-3 h-3 rounded-full bg-amber-400/60" />
                  <div className="w-3 h-3 rounded-full bg-green-400/60" />
                </div>
                <span className="text-[10px] text-muted-foreground/50 font-mono">Bapica Intelligence Engine v3</span>
              </div>

              <div className="space-y-3 font-mono text-xs">
                <div className="flex items-center gap-2 text-muted-foreground/60">
                  <span className="text-green-500">✓</span> Analyse du secteur en cours...
                </div>
                <div className="flex items-center gap-2 text-muted-foreground/60">
                  <Sparkles className="h-3 w-3 text-primary animate-pulse" />
                  <span>Identification des besoins spécifiques</span>
                </div>
                <div className="flex items-center gap-2 text-muted-foreground/60">
                  <span className="text-green-500">✓</span> Benchmarks sectoriels chargés
                </div>
                <div className="flex items-center gap-2 text-muted-foreground/60">
                  <Sparkles className="h-3 w-3 text-purple-500 animate-pulse" />
                  <span>Calcul du ROI potentiel...</span>
                </div>
                <div className="flex items-center gap-2 text-muted-foreground/60">
                  <span className="text-green-500">✓</span> Agents recommandés prêts
                </div>
                <div className="mt-4 pt-3 border-t border-border/50">
                  <div className="flex items-center gap-2">
                    <Zap className="h-3 w-3 text-amber-500" />
                    <span className="text-primary font-semibold">Diagnostic prêt</span>
                  </div>
                  <p className="mt-1 text-muted-foreground/70 leading-relaxed">
                    Score de maturité : <span className="text-primary font-bold">72/100</span> · 
                    3 agents recommandés · ROI estimé à <span className="text-green-500 font-bold">850€/mois</span>
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
