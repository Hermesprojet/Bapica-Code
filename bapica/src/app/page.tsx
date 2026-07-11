import { Navbar } from "@/components/landing/navbar"
import { Footer } from "@/components/landing/footer"

export default function HomePage() {
  return (
    <div className="min-h-screen bg-[#FAFAFA] text-[#1a1a2e]">
      <Navbar />
      
      {/* HERO */}
      <HeroSection />
      
      {/* CAPABILITÉS */}
      <CapabilitiesSection />
      
      {/* COMMENT ÇA MARCHE */}
      <HowItWorksSection />
      
      {/* ROI */}
      <ROISection />
      
      {/* GENESIS */}
      <GenesisSection />
      
      {/* AGENTS */}
      <AgentsSection />
      
      {/* PRICING */}
      <PricingSection />
      
      {/* CTA */}
      <CTASection />
      
      <Footer />
    </div>
  )
}

function HeroSection() {
  return (
    <section className="min-h-[88vh] flex items-center bg-[#FAFAFA]">
      <div className="container mx-auto max-w-7xl px-6 py-24">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-gray-200 bg-white text-sm text-gray-600 mb-8">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            Nouveau : Auto-configuration intelligente
          </div>
          
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight text-[#1a1a2e] leading-[1.1] mb-6">
            Votre PME pilotée<br />
            <span className="text-[#1a56db]">par l&apos;IA.</span>
            <br />Sans recruter.
          </h1>
          
          <p className="text-xl text-gray-500 max-w-xl mb-10 leading-relaxed">
            Bapica analyse votre business, se connecte à vos outils, 
            et vous donne un conseiller stratégique disponible 24h/24. 
            <strong className="text-[#1a1a2e]">5 minutes suffisent.</strong>
          </p>
          
          <div className="flex flex-wrap gap-4">
            <a href="/signup" className="inline-flex items-center gap-2 px-8 py-4 bg-[#1a1a2e] text-white rounded-xl font-medium hover:bg-[#2d2d44] transition-colors text-lg">
              Commencer gratuitement
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
            </a>
            <a href="#how" className="inline-flex items-center gap-2 px-8 py-4 bg-white border border-gray-200 text-[#1a1a2e] rounded-xl font-medium hover:border-gray-300 transition-colors text-lg">
              Comment ça marche
            </a>
          </div>
          
          <div className="flex items-center gap-8 mt-12 text-sm text-gray-400">
            <span className="flex items-center gap-1.5">⭐ 4.8/5</span>
            <span className="flex items-center gap-1.5">🔒 Données en France</span>
            <span className="flex items-center gap-1.5">💳 Sans CB</span>
          </div>
        </div>
      </div>
    </section>
  )
}

function CapabilitiesSection() {
  const cards = [
    { icon: "🧠", title: "Conseiller Stratégique", desc: "Un directeur commercial IA qui connaît votre secteur, vos chiffres, et vos objectifs. Conseils actionnables." },
    { icon: "📊", title: "Évaluation Business", desc: "Analyse complète de votre entreprise : forces, faiblesses, opportunités. Diagnostic en 2 minutes." },
    { icon: "🔌", title: "Connexion Universelle", desc: "Se connecte à TOUS vos outils : Gmail, Slack, CRM, compta... 77 plateformes et +." },
    { icon: "⚡", title: "Auto-Configuration", desc: "Zéro paramétrage. Bapica détecte votre activité et s'auto-configure en 5 minutes." },
    { icon: "🔮", title: "Pré-cognition", desc: "Anticipe vos besoins. \"Dans 3 mois, vous aurez besoin d'un CRM. Commencez à regarder.\"" },
    { icon: "🔄", title: "Orchestration", desc: "Automatise vos workflows. Facture → paiement → compta. Sans intervention humaine." },
  ]
  
  return (
    <section className="py-24 bg-white">
      <div className="container mx-auto max-w-7xl px-6">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold text-[#1a1a2e] mb-4">Bien plus qu&apos;un chatbot</h2>
          <p className="text-xl text-gray-500 max-w-2xl mx-auto">Bapica est un cortex intelligent qui comprend votre business, se connecte à votre écosystème, et agit concrètement.</p>
        </div>
        
        <div className="grid md:grid-cols-3 gap-6">
          {cards.map((card, i) => (
            <div key={i} className="group p-8 rounded-2xl border border-gray-100 bg-[#FAFAFA] hover:border-[#1a56db]/20 hover:bg-white hover:shadow-lg transition-all duration-300">
              <div className="text-4xl mb-4">{card.icon}</div>
              <h3 className="text-xl font-bold text-[#1a1a2e] mb-3">{card.title}</h3>
              <p className="text-gray-500 leading-relaxed">{card.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function HowItWorksSection() {
  const steps = [
    { step: "1", title: "Inscription", desc: "Créez votre compte en 30 secondes. Sans CB.", time: "30s" },
    { step: "2", title: "Analyse automatique", desc: "Bapica scanne votre activité, détecte vos outils, et active les bons agents.", time: "2 min" },
    { step: "3", title: "Recommandations", desc: "Votre premier diagnostic stratégique est prêt. Commencez à agir.", time: "3 min" },
  ]
  
  return (
    <section id="how" className="py-24 bg-[#FAFAFA]">
      <div className="container mx-auto max-w-7xl px-6">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold text-[#1a1a2e] mb-4">Prêt en 5 minutes</h2>
          <p className="text-xl text-gray-500">De l&apos;inscription à la première recommandation stratégique.</p>
        </div>
        
        <div className="grid md:grid-cols-3 gap-8 max-w-4xl mx-auto">
          {steps.map((s, i) => (
            <div key={i} className="relative text-center">
              {i < 2 && <div className="hidden md:block absolute top-8 left-[60%] w-full h-px bg-gray-200" />}
              <div className="w-16 h-16 rounded-2xl bg-[#1a1a2e] text-white flex items-center justify-center text-2xl font-bold mx-auto mb-4">{s.step}</div>
              <h3 className="text-lg font-bold text-[#1a1a2e] mb-2">{s.title}</h3>
              <p className="text-gray-500 text-sm mb-2">{s.desc}</p>
              <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-full">{s.time}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function ROISection() {
  const stats = [
    { value: "47h", label: "économisées par mois" },
    { value: "12K€", label: "de valeur créée / mois" },
    { value: "201", label: "fiches d'expertise" },
    { value: "77", label: "plateformes connectables" },
  ]
  
  return (
    <section className="py-20 bg-white border-y border-gray-100">
      <div className="container mx-auto max-w-7xl px-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {stats.map((s, i) => (
            <div key={i}>
              <div className="text-4xl md:text-5xl font-bold text-[#1a56db] mb-2">{s.value}</div>
              <div className="text-gray-500 text-sm">{s.label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function GenesisSection() {
  const features = [
    { title: "Détection automatique", desc: "Bapica identifie votre secteur, votre taille et vos outils sans questionnaire." },
    { title: "Prédictions à 3 mois", desc: "Anticipez les besoins avant qu'ils ne deviennent des urgences." },
    { title: "Workflows intelligents", desc: "Vos outils connectés travaillent ensemble. Zéro friction." },
  ]
  
  return (
    <section className="py-24 bg-[#FAFAFA]">
      <div className="container mx-auto max-w-7xl px-6">
        <div className="max-w-4xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-gray-200 bg-white text-sm text-gray-600 mb-6">
            ⚡ Bapica Genesis
          </div>
          <h2 className="text-4xl font-bold text-[#1a1a2e] mb-4">Zéro configuration. 100% d&apos;intelligence.</h2>
          <p className="text-xl text-gray-500 mb-12">Bapica s&apos;auto-configure en observant votre activité. Vous n&apos;avez rien à paramétrer.</p>
          
          <div className="space-y-4">
            {features.map((f, i) => (
              <div key={i} className="flex items-start gap-4 p-6 bg-white rounded-2xl border border-gray-100">
                <div className="w-8 h-8 rounded-full bg-[#1a56db]/10 flex items-center justify-center text-[#1a56db] font-bold text-sm shrink-0 mt-1">{i + 1}</div>
                <div>
                  <h3 className="font-bold text-[#1a1a2e] mb-1">{f.title}</h3>
                  <p className="text-gray-500">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

function AgentsSection() {
  const agents = [
    { name: "Conseiller Croissance", role: "Stratégie & Prospection", icon: "📈" },
    { name: "Expert Comptable", role: "Finance & Trésorerie", icon: "📊" },
    { name: "Support Client", role: "Service & Satisfaction", icon: "🎧" },
    { name: "Recruteur", role: "RH & Talents", icon: "👔" },
    { name: "Juridique", role: "Contrats & Conformité", icon: "⚖️" },
    { name: "Analytics", role: "Données & KPIs", icon: "📉" },
  ]
  
  return (
    <section className="py-24 bg-white">
      <div className="container mx-auto max-w-7xl px-6">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold text-[#1a1a2e] mb-4">12 agents experts. Une seule plateforme.</h2>
          <p className="text-xl text-gray-500 max-w-2xl mx-auto">Chaque agent est spécialisé dans son domaine. Ils travaillent ensemble pour votre réussite.</p>
        </div>
        
        <div className="grid md:grid-cols-3 gap-4 max-w-4xl mx-auto">
          {agents.map((a, i) => (
            <div key={i} className="flex items-center gap-4 p-5 rounded-2xl border border-gray-100 hover:border-[#1a56db]/20 hover:bg-[#FAFAFA] transition-all">
              <div className="text-3xl">{a.icon}</div>
              <div>
                <div className="font-bold text-[#1a1a2e]">{a.name}</div>
                <div className="text-sm text-gray-400">{a.role}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function PricingSection() {
  return (
    <section className="py-24 bg-[#FAFAFA]">
      <div className="container mx-auto max-w-7xl px-6">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold text-[#1a1a2e] mb-4">Simple, transparent</h2>
          <p className="text-xl text-gray-500">Un tarif unique. Toute la puissance.</p>
        </div>
        
        <div className="grid md:grid-cols-2 gap-8 max-w-3xl mx-auto">
          {[
            { name: "Essentiel", price: "49€", features: ["12 agents IA", "Connexions illimitées", "Conseiller stratégique", "Auto-configuration", "Support par email"] },
            { name: "Pro", price: "79€", features: ["Tout Essentiel +", "Agent téléphone 24/7", "Création vidéo", "Analyse avancée", "Support prioritaire"], popular: true },
          ].map((plan, i) => (
            <div key={i} className={`relative p-10 rounded-3xl border-2 ${plan.popular ? 'border-[#1a56db] bg-white shadow-xl' : 'border-gray-100 bg-white'}`}>
              {plan.popular && <div className="absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1 bg-[#1a56db] text-white text-sm font-medium rounded-full">Le plus choisi</div>}
              <div className="text-2xl font-bold text-[#1a1a2e] mb-2">{plan.name}</div>
              <div className="text-5xl font-bold text-[#1a1a2e] mb-6">{plan.price}<span className="text-lg text-gray-400">/mois</span></div>
              <ul className="space-y-3 mb-8">
                {plan.features.map((f, j) => (
                  <li key={j} className="flex items-center gap-2 text-gray-600">
                    <svg className="w-5 h-5 text-emerald-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                    {f}
                  </li>
                ))}
              </ul>
              <a href="/signup" className={`block text-center py-4 rounded-xl font-medium transition-colors ${plan.popular ? 'bg-[#1a56db] text-white hover:bg-[#1550c0]' : 'bg-[#1a1a2e] text-white hover:bg-[#2d2d44]'}`}>Commencer</a>
            </div>
          ))}
        </div>
        
        <p className="text-center text-gray-400 text-sm mt-8">Essai gratuit 15 jours. Sans engagement. Annulation en 1 clic.</p>
      </div>
    </section>
  )
}

function CTASection() {
  return (
    <section className="py-24 bg-[#1a1a2e] text-white">
      <div className="container mx-auto max-w-4xl px-6 text-center">
        <h2 className="text-4xl font-bold mb-4">Prêt à transformer votre PME ?</h2>
        <p className="text-xl text-gray-400 mb-10 max-w-xl mx-auto">Rejoignez les PME qui pilotent leur croissance avec l&apos;IA. Sans recruter.</p>
        <a href="/signup" className="inline-flex items-center gap-2 px-10 py-5 bg-white text-[#1a1a2e] rounded-xl font-bold text-lg hover:bg-gray-100 transition-colors">
          Démarrer gratuitement
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
        </a>
      </div>
    </section>
  )
}
