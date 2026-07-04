import { Navbar } from "@/components/landing/navbar"
import { HeroSection } from "@/components/landing/hero-section"
import { NeedsFinder } from "@/components/landing/needs-finder"
import { LiveDemo } from "@/components/landing/live-demo"
import { FeaturesSection } from "@/components/landing/features-section"
import { UseCasesSection } from "@/components/landing/use-cases-section"
import { AgentsSection } from "@/components/landing/agents-section"
import { PricingSection } from "@/components/landing/pricing-section"
import { TestimonialsSection } from "@/components/landing/testimonials-section"
import { ComparisonSection } from "@/components/landing/comparison-section"
import { FAQSection } from "@/components/landing/faq-section"
import { CTASection } from "@/components/landing/cta-section"
import { Footer } from "@/components/landing/footer"

export default function Home() {
  return (
    <>
      <Navbar />
      <main>
        <HeroSection />
        <NeedsFinder />
        <LiveDemo />
        <FeaturesSection />
        <UseCasesSection />
        <AgentsSection />
        <PricingSection />
        <TestimonialsSection />
        <ComparisonSection />
        <FAQSection />
        <CTASection />
      </main>
      <Footer />
    </>
  )
}
