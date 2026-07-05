import { Phone, FileText, TrendingUp, HeadphonesIcon } from 'lucide-react'

const useCases = [
  {
    icon: Phone,
    title: 'Agent Commercial',
    subtitle: 'Prospection & closing automatisé',
    gradient: 'from-orange-500 to-amber-500',
    description: 'Elio prospecte sur LinkedIn et par téléphone. Il qualifie les leads, prend les RDV et alimente votre CRM. Vous ne relancez plus jamais un prospect froid.',
    benefits: ['50 appels/jour en simultané', 'Qualification automatique des leads', 'Synchro calendrier + CRM'],
  },
  {
    icon: HeadphonesIcon,
    title: 'Support Client',
    subtitle: 'Standard téléphonique IA 24/7',
    gradient: 'from-emerald-500 to-green-500',
    description: 'Tom répond à vos clients par téléphone et WhatsApp, 24h/24. Il filtre les démarchages, prend les messages et planifie les rappels.',
    benefits: ['0 appel perdu', 'Réponse en 3 secondes', '140 langues disponibles'],
  },
  {
    icon: FileText,
    title: 'Comptabilité & Admin',
    subtitle: 'Factures, relances, tableaux de bord',
    gradient: 'from-amber-500 to-yellow-500',
    description: 'Manue gère vos factures, relances impayés, TVA et prévisionnel. Elle vous alerte sur les échéances URSSAF et optimise votre trésorerie.',
    benefits: ['Factures automatisées', 'Relances intelligentes', 'Prévisions financières'],
  },
  {
    icon: TrendingUp,
    title: 'Marketing & SEO',
    subtitle: 'Contenu, réseaux sociaux, référencement',
    gradient: 'from-indigo-500 to-blue-500',
    description: 'John et Lou créent vos posts réseaux, articles SEO optimisés et visuels. Publication automatique sur WordPress, LinkedIn et Instagram.',
    benefits: ['1 article SEO/jour', 'Posts multi-plateformes', 'Audit concurrentiel automatique'],
  },
]

export function UseCasesSection() {
  return (
    <section id="use-cases" className="relative border-t border-border py-20 md:py-28 overflow-hidden">
      <div className="absolute inset-0 bg-grid opacity-30" />
      
      <div className="container mx-auto px-4 relative">
        <div className="mx-auto mb-4 max-w-2xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary mb-6">
            🎯 Cas d&apos;usage
          </div>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Des solutions IA pour chaque <span className="gradient-text">métier</span>
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Que vous soyez commercial, comptable ou community manager, un agent IA spécialisé vous attend.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-2 mt-12">
          {useCases.map((uc) => (
            <div key={uc.title} className="card-professional p-5 sm:p-6 group">
              <div className="flex items-start gap-3 sm:gap-4">
                <div className={`flex h-10 w-10 sm:h-12 sm:w-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${uc.gradient} text-white shadow-sm transition-transform duration-300 group-hover:scale-110`}>
                  <uc.icon className="h-5 w-5 sm:h-6 sm:w-6" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-foreground text-sm sm:text-base">{uc.title}</h3>
                  <p className="text-xs text-muted-foreground/60 mt-0.5">{uc.subtitle}</p>
                </div>
              </div>

              <p className="mt-3 sm:mt-4 text-xs sm:text-sm text-muted-foreground/70 leading-relaxed">
                {uc.description}
              </p>

              <div className="mt-3 sm:mt-4 flex flex-wrap gap-2">
                {uc.benefits.map((b) => (
                  <span key={b} className="inline-flex items-center rounded-full bg-muted/50 px-2.5 sm:px-3 py-1 text-[11px] sm:text-xs text-muted-foreground/70 border border-border">
                    {b}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
