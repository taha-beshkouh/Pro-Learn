import { FaqSection } from '../components/home/FaqSection'
import { FinalCtaSection } from '../components/home/FinalCtaSection'
import { HeroSection } from '../components/home/HeroSection'
import { HomeFooter } from '../components/home/HomeFooter'
import { HowItWorksSection } from '../components/home/HowItWorksSection'
import { ProjectPreviewSection } from '../components/home/ProjectPreviewSection'
import { RoleCardsSection } from '../components/home/RoleCardsSection'
import { WhyUsSection } from '../components/home/WhyUsSection'
import '../styles/home.css'

export function HomePage() {
  return (
    <div className="home-page">
      <HeroSection />
      <WhyUsSection />
      <HowItWorksSection />
      <ProjectPreviewSection />
      <RoleCardsSection />
      <div className="home-faq-flow">
        <FaqSection />
        <FinalCtaSection />
      </div>
      <HomeFooter />
    </div>
  )
}
