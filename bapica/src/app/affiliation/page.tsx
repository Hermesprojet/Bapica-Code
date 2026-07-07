import Link from "next/link"
import { ArrowRight, Gift, TrendingUp, Shield, Check } from "lucide-react"

export default function AffiliationPage() {
  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto max-w-4xl px-4 pt-24 pb-16">
        <Link href="/" className="text-sm text-muted-foreground hover:text-foreground mb-8 inline-block">
          ← Retour à l&apos;accueil
        </Link>
        
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 rounded-full bg-purple-500/10 px-4 py-1.5 text-sm font-medium text-purple-500 mb-6">
            <Gift className="h-4 w-4" /> Programme Affiliation
          </div>
          <h1 className="text-3xl md:text-5xl font-bold tracking-tight">
            Recommandez Bapica.<br />
            <span className="gradient-text">Gagnez 20% à vie.</span>
          </h1>
          <p className="mt-4 text-lg text-muted-foreground max-w-2xl mx-auto">
            Chaque client que vous apportez vous rapporte 20% de commission récurrente, chaque mois, aussi longtemps qu&apos;il reste abonné.
          </p>
        </div>

        {/* How it works */}
        <div className="grid gap-6 md:grid-cols-3 mb-12">
          {[
            { step: "1", title: "Inscrivez-vous", desc: "Créez votre compte partenaire en 1 minute", icon: Gift },
            { step: "2", title: "Partagez votre lien", desc: "Recommandez Bapica à votre réseau", icon: TrendingUp },
            { step: "3", title: "Gagnez 20%", desc: "Commission récurrente à vie sur chaque client", icon: Shield },
          ].map(s => (
            <div key={s.step} className="card-professional text-center">
              <s.icon className="h-8 w-8 mx-auto mb-3 text-purple-500" />
              <div className="text-3xl font-bold text-muted-foreground/20 mb-2">{s.step}</div>
              <h3 className="font-semibold">{s.title}</h3>
              <p className="text-sm text-muted-foreground mt-1">{s.desc}</p>
            </div>
          ))}
        </div>

        {/* Calculator */}
        <div className="card-professional mb-8 p-8">
          <h3 className="text-xl font-bold text-center mb-4">💸 Simulez vos gains</h3>
          <div className="grid md:grid-cols-3 gap-4 text-center">
            {[
              { clients: "5 clients", essentiel: "49€/mois", pro: "79€/mois" },
              { clients: "10 clients", essentiel: "98€/mois", pro: "158€/mois" },
              { clients: "20 clients", essentiel: "196€/mois", pro: "316€/mois" },
            ].map(r => (
              <div key={r.clients} className="rounded-lg bg-muted/50 p-4">
                <div className="text-sm text-muted-foreground mb-2">{r.clients}</div>
                <div className="text-2xl font-bold gradient-text">{r.pro}</div>
                <div className="text-xs text-muted-foreground">en plan Pro</div>
              </div>
            ))}
          </div>
        </div>

        {/* CTA */}
        <div className="text-center">
          <Link href="/signup" className="btn-primary inline-flex">
            Devenir partenaire
            <ArrowRight className="h-4 w-4" />
          </Link>
          <p className="mt-4 text-sm text-muted-foreground">
            Des questions ? <a href="mailto:affiliation@bapica.com" className="text-primary hover:underline">affiliation@bapica.com</a>
          </p>
        </div>
      </div>
    </div>
  )
}
