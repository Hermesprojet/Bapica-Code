const testimonials = [
  {
    name: 'Sophie Moreau',
    role: 'Dirigeante d\'une agence immo',
    avatar: 'SM',
    gradient: 'from-indigo-500 to-blue-500',
    content: 'Depuis qu\'on utilise Tom, on ne rate plus un seul appel. Même quand l\'équipe est en déplacement, nos clients sont pris en charge et les rendez-vous se placent tout seuls.',
    rating: 5,
  },
  {
    name: 'Thibault Martin',
    role: 'Responsable e-commerce',
    avatar: 'TM',
    gradient: 'from-cyan-500 to-teal-500',
    content: 'Grâce à Lou, on a triplé notre trafic SEO en trois mois. Il publie un article par jour sur notre blog avec une qualité qu\'on n\'arrivait pas à tenir en interne.',
    rating: 5,
  },
  {
    name: 'Claire Dubois',
    role: 'Directrice d\'une TPE',
    avatar: 'CD',
    gradient: 'from-rose-500 to-pink-500',
    content: 'Charly, c\'est mon bras droit digital. J\'écris un message le matin, elle gère mes rendez-vous, mes mails, mon équipe IA. C\'est de la magie.',
    rating: 5,
  },
]

export function TestimonialsSection() {
  return (
    <section className="relative border-t border-border py-20 md:py-28 overflow-hidden">
      <div className="absolute top-1/3 left-1/4 h-64 w-64 rounded-full bg-primary/5 blur-[120px]" />
      
      <div className="container mx-auto px-4 relative">
        <div className="mx-auto mb-4 max-w-2xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary mb-6">
            💬 Ils parlent de nous
          </div>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Ce que nos <span className="gradient-text">clients</span> en disent
          </h2>
        </div>

        <div className="grid gap-6 md:grid-cols-3 mt-12">
          {testimonials.map((t) => (
            <div key={t.name} className="card-elevated p-6 flex flex-col">
              {/* Stars */}
              <div className="flex gap-1 mb-4">
                {[...Array(t.rating)].map((_, i) => (
                  <svg key={i} className="h-4 w-4 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                  </svg>
                ))}
              </div>

              {/* Content */}
              <p className="text-sm text-muted-foreground leading-relaxed flex-1 italic">
                &ldquo;{t.content}&rdquo;
              </p>

              {/* Author */}
              <div className="flex items-center gap-3 mt-6 pt-4 border-t border-white/5">
                <div className={`flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br ${t.gradient} text-white text-xs font-bold`}>
                  {t.avatar}
                </div>
                <div>
                  <p className="text-sm font-medium">{t.name}</p>
                  <p className="text-xs text-muted-foreground">{t.role}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
