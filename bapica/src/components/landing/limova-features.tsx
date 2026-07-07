import Link from "next/link"
import { ArrowRight, MessageCircle, Sparkles, Gift, Users } from "lucide-react"

export function LimovaFeatures() {
  return (
    <section className="border-t border-border py-16 md:py-20 bg-muted/20">
      <div className="container mx-auto max-w-6xl px-4">
        <p className="section-label">CE QUE LIMOVA NE VOUS DIT PAS</p>
        <h2 className="text-3xl md:text-4xl font-bold tracking-tight mb-12">
          Bapica va <span className="gradient-text">plus loin</span>
        </h2>

        <div className="grid gap-8 lg:grid-cols-2">
          {/* WhatsApp / Charly+ equivalent */}
          <div className="card-professional group">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-green-500 text-white shadow-sm">
                <MessageCircle className="h-6 w-6" />
              </div>
              <div>
                <h3 className="font-semibold text-lg">WhatsApp Business intégré</h3>
                <p className="text-sm text-muted-foreground/70 mt-1">
                  Comme Charly+ chez Limova, mais en mieux. Vos agents répondent sur WhatsApp, le canal préféré des PME françaises.
                </p>
                <ul className="mt-3 space-y-1.5">
                  {["Messages illimités","Réponses instantanées 24/7","Transfert vers agent humain si nécessaire"].map(f => (
                    <li key={f} className="flex items-center gap-2 text-sm text-muted-foreground">
                      <span className="text-green-500">✓</span> {f}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          {/* Onboarding */}
          <div className="card-professional group">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-blue-500 text-white shadow-sm">
                <Sparkles className="h-6 w-6" />
              </div>
              <div>
                <h3 className="font-semibold text-lg">Onboarding intelligent</h3>
                <p className="text-sm text-muted-foreground/70 mt-1">
                  En 5 minutes, notre IA analyse vos besoins et configure automatiquement votre équipe d&apos;agents. Pas besoin d&apos;attendre un rendez-vous humain.
                </p>
                <ul className="mt-3 space-y-1.5">
                  {["Diagnostic automatique","Recommandation personnalisée","Prêt en 5 minutes"].map(f => (
                    <li key={f} className="flex items-center gap-2 text-sm text-muted-foreground">
                      <span className="text-blue-500">✓</span> {f}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          {/* Affiliation */}
          <div className="card-professional group">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-purple-500 text-white shadow-sm">
                <Gift className="h-6 w-6" />
              </div>
              <div>
                <h3 className="font-semibold text-lg">Programme Affiliation</h3>
                <p className="text-sm text-muted-foreground/70 mt-1">
                  Recommandez Bapica et gagnez <strong>20% de commission récurrente</strong> sur chaque client que vous apportez.
                </p>
                <Link href="/affiliation" className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline">
                  Rejoindre le programme <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            </div>
          </div>

          {/* Contact direct */}
          <div className="card-professional group">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-amber-500 text-white shadow-sm">
                <Users className="h-6 w-6" />
              </div>
              <div>
                <h3 className="font-semibold text-lg">Une vraie équipe derrière l&apos;IA</h3>
                <p className="text-sm text-muted-foreground/70 mt-1">
                  Besoin d&apos;aide ? Notre équipe est disponible par email et vous répond en moins de 4h.
                </p>
                <a href="mailto:contact@bapica.com" className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline">
                  contact@bapica.com <ArrowRight className="h-3.5 w-3.5" />
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
