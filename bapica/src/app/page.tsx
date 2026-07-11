import { Navbar } from "@/components/landing/navbar"
import { Footer } from "@/components/landing/footer"

export default function HomePage() {
  return (
    <div className="min-h-screen bg-white text-[#111827]">
      <Navbar />
      <Hero />
      <Garanties />
      <Capacites />
      <Fonctionnement />
      <Chiffres />
      <Agents />
      <Connecteurs />
      <Pricing />
      <CTAFinal />
      <Footer />
    </div>
  )
}

// ─── HERO ──────────────────────────────────────────────────
function Hero() {
  return (
    <section className="min-h-[85vh] flex items-center bg-white">
      <div className="container mx-auto max-w-7xl px-6 py-24">
        <div className="max-w-4xl">
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight text-[#111827] leading-[1.08] mb-8">
            Automatisez votre entreprise<br />
            <span className="text-[#2563EB]">avec 12 agents intelligents.</span>
          </h1>
          <p className="text-xl md:text-2xl text-[#6B7280] max-w-2xl mb-12 leading-relaxed">
            Bapica se connecte à vos outils, analyse votre activité et met au travail 
            une équipe d&apos;agents spécialisés. Prospecter, facturer, recruter, 
            décider : ils gèrent. Vous pilotez.
          </p>
          <p className="text-sm text-[#9CA3AF] mb-8">
            📱 Disponible sur navigateur, WhatsApp, Messenger et Telegram
          </p>
          <div className="flex flex-wrap gap-4">
            <a href="/signup" className="inline-flex items-center gap-2 px-8 py-4 bg-[#2563EB] text-white rounded-lg font-semibold hover:bg-[#1D4ED8] transition-colors text-lg">
              Essayer gratuitement 15 jours
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
            </a>
            <a href="#fonctionnement" className="inline-flex items-center gap-2 px-8 py-4 border border-[#E5E7EB] text-[#111827] rounded-lg font-semibold hover:border-[#D1D5DB] transition-colors text-lg">
              Découvrir
            </a>
          </div>
        </div>
      </div>
    </section>
  )
}

// ─── GARANTIES ─────────────────────────────────────────────
function Garanties() {
  const items = ["Hébergé en France", "Conforme RGPD", "Sans carte bancaire", "Annulation en 1 clic"]
  return (
    <section className="border-y border-[#F3F4F6] bg-white">
      <div className="container mx-auto max-w-7xl px-6 py-4">
        <div className="flex flex-wrap justify-center gap-8 text-sm text-[#9CA3AF]">
          {items.map((item, i) => (
            <span key={i} className="flex items-center gap-1.5">
              <svg className="w-4 h-4 text-[#10B981]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
              {item}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── CAPACITÉS ─────────────────────────────────────────────
function Capacites() {
  const cards = [
    { num: "01", title: "Conseiller stratégique", desc: "Un directeur commercial IA qui connaît votre secteur, vos chiffres, vos objectifs. Recommandations actionnables, pas de généralités." },
    { num: "02", title: "Évaluation business", desc: "Analyse complète de votre entreprise en 2 minutes. Forces, faiblesses, opportunités, risques. Score de maturité." },
    { num: "03", title: "Connexion universelle", desc: "Se branche à vos outils existants. Gmail, Stripe, Pennylane, HubSpot, Shopify… 77 plateformes et toutes les autres." },
    { num: "04", title: "Auto‑configuration", desc: "Zéro paramétrage. Bapica détecte votre métier, votre taille, votre stack et active les bons agents automatiquement." },
    { num: "05", title: "Pré‑cognition", desc: "Anticipe vos besoins avant qu&apos;ils ne deviennent des urgences. \"Dans 3 mois, vous aurez besoin de…\"" },
    { num: "06", title: "Orchestration", desc: "Automatise vos flux de travail. Facture → paiement → compta. Lead → CRM → relance. Sans lever le petit doigt." },
  ]

  return (
    <section className="py-24 bg-[#F9FAFB]">
      <div className="container mx-auto max-w-7xl px-6">
        <div className="mb-16">
          <p className="text-sm font-medium text-[#2563EB] uppercase tracking-wider mb-4">Capacités</p>
          <h2 className="text-4xl md:text-5xl font-bold text-[#111827] mb-4">Bien plus qu&apos;un chatbot.</h2>
          <p className="text-xl text-[#6B7280] max-w-2xl">Un cortex intelligent qui comprend votre business, se connecte à votre écosystème et agit concrètement.</p>
        </div>

        <div className="grid md:grid-cols-3 gap-px bg-[#E5E7EB] rounded-2xl overflow-hidden">
          {cards.map((card, i) => (
            <div key={i} className="bg-white p-10 hover:bg-[#F9FAFB] transition-colors">
              <div className="text-3xl font-bold text-[#2563EB]/20 mb-6">{card.num}</div>
              <h3 className="text-lg font-bold text-[#111827] mb-3">{card.title}</h3>
              <p className="text-[#6B7280] leading-relaxed">{card.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── FONCTIONNEMENT ────────────────────────────────────────
function Fonctionnement() {
  const steps = [
    { num: "01", title: "Créez votre compte", desc: "30 secondes. Sans carte bancaire.", icon: "👤" },
    { num: "02", title: "Bapica analyse", desc: "Détection automatique de votre activité, vos outils, vos besoins.", icon: "🔍" },
    { num: "03", title: "Vos agents travaillent", desc: "Premières recommandations stratégiques en moins de 5 minutes.", icon: "🚀" },
  ]

  return (
    <section id="fonctionnement" className="py-24 bg-white">
      <div className="container mx-auto max-w-7xl px-6">
        <div className="mb-16">
          <p className="text-sm font-medium text-[#2563EB] uppercase tracking-wider mb-4">Fonctionnement</p>
          <h2 className="text-4xl md:text-5xl font-bold text-[#111827] mb-4">Prêt en 5 minutes.</h2>
          <p className="text-xl text-[#6B7280]">De l&apos;inscription à la première recommandation stratégique.</p>
        </div>

        <div className="grid md:grid-cols-3 gap-16 max-w-5xl mx-auto">
          {steps.map((s, i) => (
            <div key={i} className="relative">
              {i < 2 && <div className="hidden md:block absolute top-8 left-[60%] w-full h-px bg-[#E5E7EB]" />}
              <div className="text-4xl mb-4">{s.icon}</div>
              <div className="text-sm font-bold text-[#2563EB] mb-2">{s.num}</div>
              <h3 className="text-xl font-bold text-[#111827] mb-2">{s.title}</h3>
              <p className="text-[#6B7280]">{s.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── CHIFFRES ──────────────────────────────────────────────
function Chiffres() {
  const stats = [
    { value: "5 min", label: "De mise en route" },
    { value: "47h", label: "Économisées par mois" },
    { value: "77", label: "Plateformes connectables" },
    { value: "12", label: "Agents 24/7" },
  ]

  return (
    <section className="py-24 bg-[#111827] text-white">
      <div className="container mx-auto max-w-7xl px-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-12 text-center">
          {stats.map((s, i) => (
            <div key={i}>
              <div className="text-5xl md:text-6xl font-bold text-white mb-2">{s.value}</div>
              <div className="text-[#9CA3AF] text-lg">{s.label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── AGENTS ────────────────────────────────────────────────
function Agents() {
  const agents = [
    "Conseiller croissance", "Expert‑comptable", "Support client",
    "Recruteur", "Juridique", "Data analyst", "Veille stratégique",
    "Téléphone", "Vidéo", "Vocal", "Rédaction", "Assistant général"
  ]

  return (
    <section className="py-24 bg-white">
      <div className="container mx-auto max-w-7xl px-6">
        <div className="max-w-4xl">
          <p className="text-sm font-medium text-[#2563EB] uppercase tracking-wider mb-4">Agents</p>
          <h2 className="text-4xl md:text-5xl font-bold text-[#111827] mb-4">12 spécialistes au service de votre PME.</h2>
          <p className="text-xl text-[#6B7280] mb-12">Ils collaborent entre eux. Ils apprennent de votre activité. Ils agissent 24/7.</p>
          <div className="flex flex-wrap gap-3">
            {agents.map((a, i) => (
              <span key={i} className="px-4 py-2 bg-[#F3F4F6] text-[#374151] rounded-lg text-sm font-medium hover:bg-[#E5E7EB] transition-colors">{a}</span>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

// ─── CONNECTEURS ───────────────────────────────────────────
function Connecteurs() {
  const plateformes = ["Gmail", "Outlook", "Slack", "Teams", "Stripe", "Pennylane", "HubSpot", "Salesforce", "Shopify", "Notion", "GitHub", "PayPal", "QuickBooks", "Zapier", "Make", "Google Calendar", "Calendly", "Brevo"]

  return (
    <section className="py-24 bg-[#F9FAFB]">
      <div className="container mx-auto max-w-7xl px-6">
        <div className="mb-16">
          <p className="text-sm font-medium text-[#2563EB] uppercase tracking-wider mb-4">Connecteurs</p>
          <h2 className="text-4xl md:text-5xl font-bold text-[#111827] mb-4">Vos outils. Enfin connectés.</h2>
          <p className="text-xl text-[#6B7280] max-w-2xl">Bapica se branche à vos plateformes existantes — et à toutes les autres — sans développement.</p>
        </div>
        <div className="flex flex-wrap gap-3">
          {plateformes.map((p, i) => (
            <span key={i} className="px-4 py-2 bg-white border border-[#E5E7EB] text-[#6B7280] rounded-lg text-sm hover:border-[#2563EB] hover:text-[#2563EB] transition-colors">{p}</span>
          ))}
          <span className="px-4 py-2 bg-[#2563EB]/5 border border-[#2563EB]/20 text-[#2563EB] rounded-lg text-sm font-medium">+ toutes les API</span>
        </div>
      </div>
    </section>
  )
}

// ─── PRICING ───────────────────────────────────────────────
function Pricing() {
  const plans = [
    { name: "Essentiel", price: "49€", desc: "Pour démarrer l&apos;automatisation", features: ["12 agents IA", "5 connexions", "Auto‑configuration", "Conseiller stratégique", "Support email 48h"] },
    { name: "Pro", price: "79€", desc: "Pour les PME en croissance", features: ["12 agents IA", "Connexions illimitées", "Auto‑configuration avancée", "Conseiller stratégique prioritaire", "Support dédié < 2h", "Analyses prédictives", "Orchestration workflows"], highlight: true },
  ]

  return (
    <section className="py-24 bg-white">
      <div className="container mx-auto max-w-7xl px-6">
        <div className="text-center mb-16">
          <p className="text-sm font-medium text-[#2563EB] uppercase tracking-wider mb-4">Prix</p>
          <h2 className="text-4xl md:text-5xl font-bold text-[#111827] mb-4">Simple. Transparent.</h2>
          <p className="text-xl text-[#6B7280]">Essai gratuit 15 jours. Sans engagement.</p>
        </div>

        <div className="grid md:grid-cols-2 gap-8 max-w-3xl mx-auto">
          {plans.map((plan, i) => (
            <div key={i} className={`relative p-10 rounded-2xl border-2 ${plan.highlight ? 'border-[#2563EB] shadow-lg' : 'border-[#E5E7EB]'}`}>
              {plan.highlight && <div className="absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1 bg-[#2563EB] text-white text-sm font-medium rounded-full">Recommandé</div>}
              <div className="text-2xl font-bold text-[#111827] mb-1">{plan.name}</div>
              <div className="text-sm text-[#6B7280] mb-6">{plan.desc}</div>
              <div className="text-5xl font-bold text-[#111827] mb-8">{plan.price}<span className="text-lg text-[#9CA3AF] font-normal">/mois</span></div>
              <ul className="space-y-3 mb-8">
                {plan.features.map((f, j) => (
                  <li key={j} className="flex items-center gap-2.5 text-[#4B5563]">
                    <svg className="w-5 h-5 text-[#10B981] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                    {f}
                  </li>
                ))}
              </ul>
              <a href="/signup" className={`block text-center py-4 rounded-lg font-semibold transition-colors ${plan.highlight ? 'bg-[#2563EB] text-white hover:bg-[#1D4ED8]' : 'bg-[#111827] text-white hover:bg-[#1F2937]'}`}>Essayer gratuitement</a>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── CTA FINAL ─────────────────────────────────────────────
function CTAFinal() {
  return (
    <section className="py-24 bg-[#111827]">
      <div className="container mx-auto max-w-4xl px-6 text-center">
        <h2 className="text-4xl md:text-5xl font-bold text-white mb-4">Prêt à mettre l&apos;IA au travail ?</h2>
        <p className="text-xl text-[#9CA3AF] mb-10 max-w-xl mx-auto">Rejoignez les PME qui automatisent leur croissance. 5 minutes suffisent.</p>
        <div className="flex flex-wrap justify-center gap-4">
          <a href="/signup" className="inline-flex items-center gap-2 px-10 py-5 bg-[#2563EB] text-white rounded-lg font-bold text-lg hover:bg-[#1D4ED8] transition-colors">
            Démarrer gratuitement
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
          </a>
        </div>
        <p className="text-sm text-[#6B7280] mt-6">Aucune carte bancaire requise • Annulation en un clic</p>
      </div>
    </section>
  )
}
