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
    gradient: 'from-violet-500 to-purple-500',
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
            <div key={uc.title} className="card-elevated p-6 group">
              <div className="flex items-start gap-4">
                <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${uc.gradient} text-white shadow-lg transition-transform duration-300 group-hover:scale-110`}>
                  <uc.icon className="h-6 w-6" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold group-hover:text-primary transition-colors">{uc.title}</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">{uc.subtitle}</p>
                </div>
              </div>

              <p className="mt-4 text-sm text-muted-foreground leading-relaxed">
                {uc.description}
              </p>

              <div className="mt-4 flex flex-wrap gap-2">
                {uc.benefits.map((b) => (
                  <span key={b} className="inline-flex items-center rounded-full bg-white/[0.04] px-3 py-1 text-xs text-muted-foreground border border-white/5">
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
