import Link from "next/link"

export function HeroSection() {
  return (
    <section className="relative overflow-hidden pt-32 pb-20 md:pt-40 md:pb-28">
      {/* Background effects */}
      <div className="absolute inset-0 bg-grid" />
      <div className="absolute top-[-20%] left-[-10%] h-[500px] w-[500px] rounded-full bg-primary/10 blur-[120px] animate-pulse-glow" />
      <div className="absolute bottom-[-10%] right-[-10%] h-[400px] w-[400px] rounded-full bg-purple-500/10 blur-[100px] animate-float" />
      
      <div className="container mx-auto px-4 text-center relative">
        {/* Badge */}
        <div className="mx-auto mb-8 inline-flex animate-slide-up items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-sm backdrop-blur-sm">
          <span className="flex h-2 w-2">
            <span className="absolute inline-flex h-2 w-2 animate-ping rounded-full bg-green-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
          </span>
          <span className="text-muted-foreground">
            <span className="font-semibold text-foreground">Jusqu&apos;à 12 agents IA</span> prêts à l&apos;emploi
          </span>
        </div>

        {/* Title */}
        <h1 className="animate-slide-up animate-delay-1 mx-auto max-w-5xl text-4xl font-bold tracking-tight sm:text-5xl md:text-6xl lg:text-7xl leading-[1.1]">
          Vos <span className="gradient-text">agents IA</span>{" "}
          au service de votre{" "}
          <span className="gradient-text">entreprise</span>
        </h1>

        {/* Subtitle */}
        <p className="animate-slide-up animate-delay-2 mx-auto mt-6 max-w-2xl text-lg text-muted-foreground leading-relaxed">
          Prospection, support client, contenu, voix, recrutement, comptabilité&hellip;
          Une équipe complète d&apos;agents IA pour développer votre activité, 24h/24 et 7j/7.
          <span className="block mt-1 text-sm font-medium text-primary">Aucune compétence technique requise.</span>
        </p>

        {/* CTA Buttons */}
        <div className="animate-slide-up animate-delay-3 mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
          <Link
            href="/signup"
            className="group relative inline-flex h-12 items-center justify-center rounded-lg bg-primary px-8 text-sm font-medium text-primary-foreground shadow-2xl shadow-primary/25 transition-all duration-300 hover:shadow-primary/40 hover:scale-105 overflow-hidden"
          >
            <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700" />
            <span className="relative">Commencer gratuitement</span>
            <svg className="relative ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </Link>
          <Link
            href="#diagnostic"
            className="group inline-flex h-12 items-center justify-center rounded-lg border border-border bg-background/50 backdrop-blur-sm px-8 text-sm font-medium hover:bg-muted transition-all hover:border-primary/50"
          >
            Diagnostic gratuit
            <svg className="ml-2 h-4 w-4 transition-transform group-hover:translate-y-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </Link>
        </div>

        {/* Trust indicators */}
        <div className="animate-slide-up animate-delay-4 mt-16 flex flex-wrap items-center justify-center gap-x-8 gap-y-4 text-sm text-muted-foreground">
          <div className="flex items-center gap-2 group">
            <div className="flex -space-x-2">
              {[1,2,3].map((i) => (
                <div key={i} className="h-7 w-7 rounded-full border-2 border-background bg-gradient-to-br from-primary/40 to-purple-500/40" />
              ))}
            </div>
            <span className="text-muted-foreground">+<span className="font-semibold text-foreground">30</span> bêta-testeurs</span>
          </div>
          <div className="flex items-center gap-1.5">
            {[...Array(5)].map((_, i) => (
              <svg key={i} className="h-4 w-4 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
            ))}
            <span className="ml-1 text-muted-foreground">4.9/5</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="flex h-2 w-2 rounded-full bg-green-500" />
            <span className="text-muted-foreground">Sans engagement</span>
          </div>
        </div>
      </div>
    </section>
  )
}
