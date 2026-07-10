import { VideoPresentation } from "@/components/landing/video-presentation"
import { Navbar } from "@/components/landing/navbar"
import { HeroSection } from "@/components/landing/hero-section"
import { IntelligenceSection } from "@/components/landing/intelligence-section"
import { ROIStats } from "@/components/landing/roi-stats"
import { NeedsFinder } from "@/components/landing/needs-finder"
import { FeaturesSection } from "@/components/landing/features-section"
import { UseCasesSection } from "@/components/landing/use-cases-section"
import { AgentsSection } from "@/components/landing/agents-section"
import { TeamSection } from "@/components/landing/team-section"
import { PricingSection } from "@/components/landing/pricing-section"
import { TestimonialsSection } from "@/components/landing/testimonials-section"
import { ComparisonSection } from "@/components/landing/comparison-section"
import { FAQSection } from "@/components/landing/faq-section"
import { CTASection } from "@/components/landing/cta-section"
import { Footer } from "@/components/landing/footer"

export default function Home() {
  return (
    <main>
      <h1 className="sr-only">Bapica — Agents IA pour votre entreprise | Automatisation PME</h1>
      <Navbar />
        <VideoPresentation />
        <div className="container mx-auto max-w-6xl px-4 py-16">
          <video 
            src="/bapica-11agents.mp4" 
            controls 
            poster="/opengraph-image"
            className="mx-auto w-full max-w-4xl rounded-2xl border border-white/[0.06] shadow-2xl"
            preload="metadata"
          >
            Votre navigateur ne supporte pas la lecture vidéo.
          </video>
        </div>
        <HeroSection />
        <IntelligenceSection />
        <ROIStats />
        <NeedsFinder />
        <FeaturesSection />
        <UseCasesSection />
        <AgentsSection />
        <TeamSection />
        <PricingSection />
        <TestimonialsSection />
        <ComparisonSection />
        <FAQSection />
        <CTASection />
      <Footer />
    </main>
  )
}
