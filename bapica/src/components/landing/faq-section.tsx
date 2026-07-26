"use client"

import { useState } from "react"
import { ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"

const faqs = [
  {
    q: "Comment fonctionne la plateforme ?",
    a: "Vous créez votre compte, choisissez votre formule, et accédez à vos agents IA. Chaque agent a une mission spécifique : prospection, support, contenu... Vous discutez avec eux comme avec un assistant, et ils exécutent les tâches automatiquement.",
  },
  {
    q: "Puis-je essayer avant d'acheter ?",
    a: "Oui ! Vous bénéficiez de 15 jours d'essai gratuit, sans engagement et sans carte bancaire. Tous les agents de votre formule sont accessibles pendant la période d'essai.",
  },
  {
    q: "Les agents parlent-ils vraiment plusieurs langues ?",
    a: "Absolument. Tous nos agents détectent automatiquement la langue de l'utilisateur et répondent dans cette même langue, quelle qu'elle soit, avec la même qualité.",
  },
  {
    q: "Comment se passe la facturation ?",
    a: "La facturation est mensuelle, gérée par Stripe. Vous pouvez résilier à tout moment depuis votre tableau de bord. Pas d'engagement, pas de frais cachés.",
  },
  {
    q: "Mes données sont-elles sécurisées ?",
    a: "Oui. Nous utilisons Supabase (infrastructure sécurisée), le chiffrement en transit et au repos, et nous sommes conformes RGPD. Vos données ne sont jamais partagées avec d'autres clients.",
  },
  {
    q: "Puis-je intégrer mes propres outils ?",
    a: "Oui ! La formule Pro inclut l'accès à n8n pour créer des workflows personnalisés, et l'API pour connecter vos propres outils.",
  },
  {
    q: "Qu'est-ce qui différencie Bapica des autres solutions ?",
    a: "Notre plateforme propose jusqu'à 11 agents spécialisés couvrant tous les aspects de votre activité, le tout dans une interface unifiée. Pas besoin de jongler entre 5 outils différents.",
  },
  {
    q: "Puis-je changer de formule ?",
    a: "Oui, à tout moment. Vous pouvez passer à une formule supérieure ou inférieure depuis votre tableau de bord. Les changements sont pris en compte immédiatement.",
  },
]

export function FAQSection() {
  const [openId, setOpenId] = useState<number | null>(null)

  return (
    <section id="faq" className="border-t border-border py-20 md:py-28">
      <div className="container mx-auto px-4">
        <div className="mx-auto mb-16 max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Questions fréquentes
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Tout ce que vous devez savoir avant de commencer.
          </p>
        </div>
        <div className="mx-auto max-w-3xl space-y-2">
          {faqs.map((faq, i) => (
            <div key={i} className="rounded-lg border border-border">
              <button
                onClick={() => setOpenId(openId === i ? null : i)}
                className="flex w-full items-center justify-between px-6 py-4 text-left font-medium transition-colors hover:bg-muted/50"
              >
                {faq.q}
                <ChevronDown
                  className={cn(
                    "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                    openId === i && "rotate-180"
                  )}
                />
              </button>
              {openId === i && (
                <div className="border-t border-border px-6 py-4 text-sm text-muted-foreground">
                  {faq.a}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
