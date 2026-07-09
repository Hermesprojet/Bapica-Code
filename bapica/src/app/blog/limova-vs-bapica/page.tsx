import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Limova vs Bapica — Quel agent IA choisir en 2026 ?",
  description: "Comparatif complet : Limova.ai vs Bapica. Nombre d&apos;agents, qualité IA, prix, fonctionnalités, avis. Découvrez quelle plateforme d&apos;agents IA correspond le mieux à votre PME.",
}

export default function LimovaVsBapicaPage() {
  return (
    <main className="min-h-screen bg-background py-16">
      <article className="mx-auto max-w-3xl px-4">
        <h1 className="mb-6 text-4xl font-bold text-foreground">
          Limova vs Bapica — Quel agent IA choisir en 2026 ?
        </h1>

        <p className="mb-8 text-lg text-muted-foreground">
          Vous cherchez à automatiser votre PME avec des agents IA ? Voici un comparatif objectif entre Limova.ai 
          et Bapica, les deux principales plateformes françaises d&apos;agents IA pour les indépendants et PME.
        </p>

        {/* Tableau comparatif */}
        <div className="mb-10 overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-border">
                <th className="py-3 text-left text-sm font-medium text-muted-foreground">Critère</th>
                <th className="py-3 text-left text-sm font-medium text-blue-600">Limova.ai</th>
                <th className="py-3 text-left text-sm font-medium text-foreground">Bapica</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              <tr>
                <td className="py-3 text-sm font-medium">Nombre d&apos;agents</td>
                <td className="py-3 text-sm">8 agents</td>
                <td className="py-3 text-sm font-semibold">✅ 13 agents spécialisés</td>
              </tr>
              <tr>
                <td className="py-3 text-sm font-medium">Modèle IA</td>
                <td className="py-3 text-sm">GPT-4o-mini</td>
                <td className="py-3 text-sm font-semibold">✅ Claude Sonnet + GPT-4o</td>
              </tr>
              <tr>
                <td className="py-3 text-sm font-medium">Intelligence business</td>
                <td className="py-3 text-sm">Non</td>
                <td className="py-3 text-sm font-semibold">✅ Score santé, ROI, benchmarks</td>
              </tr>
              <tr>
                <td className="py-3 text-sm font-medium">WhatsApp</td>
                <td className="py-3 text-sm font-semibold">✅ Charly+ sur WhatsApp</td>
                <td className="py-3 text-sm">Web app native</td>
              </tr>
              <tr>
                <td className="py-3 text-sm font-medium">Dashboard analytics</td>
                <td className="py-3 text-sm">Non</td>
                <td className="py-3 text-sm font-semibold">✅ Dashboard intelligent</td>
              </tr>
              <tr>
                <td className="py-3 text-sm font-medium">Prix entrée</td>
                <td className="py-3 text-sm font-semibold">~39€/mois</td>
                <td className="py-3 text-sm">49€/mois</td>
              </tr>
              <tr>
                <td className="py-3 text-sm font-medium">Essai gratuit</td>
                <td className="py-3 text-sm">Oui</td>
                <td className="py-3 text-sm font-semibold">✅ 15 jours sans CB</td>
              </tr>
              <tr>
                <td className="py-3 text-sm font-medium">Onboarding</td>
                <td className="py-3 text-sm font-semibold">Humain 1:1</td>
                <td className="py-3 text-sm font-semibold">✅ IA + humain</td>
              </tr>
              <tr>
                <td className="py-3 text-sm font-medium">Coordination agents</td>
                <td className="py-3 text-sm">Non</td>
                <td className="py-3 text-sm font-semibold">✅ Léo, agent coordinateur</td>
              </tr>
            </tbody>
          </table>
        </div>

        <h2 className="mb-4 mt-12 text-2xl font-bold">Quand choisir Limova ?</h2>
        <ul className="mb-8 space-y-2 text-muted-foreground">
          <li>• Vous voulez interagir avec vos agents via WhatsApp</li>
          <li>• Vous préférez un onboarding humain (RDV téléphonique)</li>
          <li>• Votre budget est serré et 39€/mois fait la différence</li>
          <li>• Vous avez besoin d&apos;un standard téléphonique simple</li>
        </ul>

        <h2 className="mb-4 mt-12 text-2xl font-bold">Quand choisir Bapica ?</h2>
        <ul className="mb-8 space-y-2 text-muted-foreground">
          <li>• Vous voulez une IA qui comprend vraiment votre métier</li>
          <li>• Vous avez besoin de plusieurs agents qui collaborent</li>
          <li>• Le dashboard et le suivi ROI sont importants pour vous</li>
          <li>• Vous voulez la meilleure qualité d&apos;IA (Claude Sonnet)</li>
          <li>• Vous cherchez plus que du standard téléphonique</li>
        </ul>

        <h2 className="mb-4 mt-12 text-2xl font-bold">Verdict</h2>
        <p className="mb-2 text-muted-foreground">
          Limova est un excellent choix si vous voulez la simplicité de WhatsApp et un onboarding humain.
        </p>
        <p className="mb-2 text-muted-foreground">
          Bapica est le choix stratégique si vous voulez une <strong>plateforme complète</strong> avec 
          une IA plus performante, un dashboard de pilotage, et une coordination intelligente entre agents.
        </p>
        <p className="text-muted-foreground">
          Notre recommandation ? <strong>Testez les deux</strong> — Limova et Bapica offrent des essais gratuits.
          Comparez par vous-même la qualité des réponses et l&apos;adaptation à votre business.
        </p>

        <div className="mt-12 rounded-lg border border-border bg-card p-6 text-center">
          <p className="mb-4 text-lg font-semibold">Analysez votre business gratuitement</p>
          <p className="mb-6 text-sm text-muted-foreground">
            5 minutes pour découvrir quels agents IA vous feront gagner du temps.
          </p>
          <a
            href="/signup"
            className="inline-block rounded-lg bg-foreground px-6 py-3 text-sm font-medium text-background hover:opacity-90"
          >
            Essai gratuit — 15 jours
          </a>
        </div>
      </article>
    </main>
  )
}
