import { Navbar } from "@/components/landing/navbar"
import { HeroSection } from "@/components/landing/hero-section"
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
    <>
      <Navbar />
      <main>
        <HeroSection />
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
      </main>
      <Footer />
    </>
  )
}
