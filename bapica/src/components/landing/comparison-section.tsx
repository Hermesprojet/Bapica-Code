import { Check } from 'lucide-react'

const comparison = [
  { feature: 'Agents IA spécialisés', us: '10 experts métier', them: '8 agents génériques' },
  { feature: 'Messages', us: 'Illimités', them: 'Illimités' },
  { feature: 'Appels vocaux', us: '0,20€/min', them: '0,20€/min' },
  { feature: 'Onboarding personnalisé', us: 'Questionnaire intelligent ✓', them: 'Standard' },
  { feature: 'Dashboard adaptatif', us: 'Widgets selon vos besoins ✓', them: 'Fixe' },
  { feature: 'Prix', us: 'À partir de 49€/mois', them: 'À partir de 39€/mois' },
  { feature: 'Hébergement', us: 'Vercel Edge (mondial)', them: 'Render (US)' },
  { feature: 'IA générative', us: 'Claude Haiku + Sonnet', them: 'GPT-4o + 4o-mini' },
]

export function ComparisonSection() {
  return (
    <section className="relative border-t border-border py-20 md:py-28 overflow-hidden">
      <div className="absolute inset-0 bg-grid opacity-30" />
      <div className="container mx-auto px-4 relative">
        <div className="mx-auto mb-4 max-w-2xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary mb-6">
            ⚡ Comparatif
          </div>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Pourquoi choisir <span className="gradient-text">Bapica</span>
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Plus d&apos;agents, plus de fonctionnalités, au meilleur prix.
          </p>
        </div>

        <div className="mx-auto max-w-3xl overflow-hidden rounded-2xl border border-border bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="px-6 py-4 text-left font-semibold text-foreground">Fonctionnalité</th>
                <th className="px-6 py-4 text-center font-semibold">
                  <span className="gradient-text">Bapica</span>
                </th>
                <th className="px-6 py-4 text-center font-semibold text-muted-foreground">Autres</th>
              </tr>
            </thead>
            <tbody>
              {comparison.map((row, i) => (
                <tr key={row.feature} className={`border-b border-border transition-colors hover:bg-muted/50 ${row.us.startsWith('Bientôt') ? 'opacity-60' : ''}`}>
                  <td className="px-6 py-3.5 text-muted-foreground">{row.feature}</td>
                  <td className="px-6 py-3.5 text-center">
                    <span className={`inline-flex items-center gap-1.5 font-medium ${row.us.startsWith('✓') || row.us.startsWith('Bientôt') ? 'text-primary' : 'text-foreground'}`}>
                      {row.us.startsWith('✓') ? <Check className="h-3.5 w-3.5 text-green-400" /> : null}
                      {row.us}
                    </span>
                  </td>
                  <td className="px-6 py-3.5 text-center text-muted-foreground">{row.them}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-8 text-center">
          <p className="text-xs text-muted-foreground">
            Comparaison basée sur les offres publiques de nos concurrents au moment de l&apos;analyse.
          </p>
        </div>
      </div>
    </section>
  )
}
