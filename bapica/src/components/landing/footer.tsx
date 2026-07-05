import Link from "next/link"
import { Logo } from "@/components/brand/logo"

export function Footer() {
  return (
    <footer className="border-t border-border py-12">
      <div className="container mx-auto px-4">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <Logo />

            <p className="mt-4 text-sm text-muted-foreground">
              Plateforme multi-agents IA pour PME et indépendants.
            </p>
          </div>
          <div>
            <h4 className="mb-4 text-sm font-semibold">Agents</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link href="/agents/general" className="hover:text-foreground transition-colors">Agent Général</Link></li>
              <li><Link href="/agents/support" className="hover:text-foreground transition-colors">Support Client</Link></li>
              <li><Link href="/agents/telephone" className="hover:text-foreground transition-colors">Agent Téléphonique</Link></li>
              <li><Link href="/agents/content" className="hover:text-foreground transition-colors">Créateur de Contenu</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="mb-4 text-sm font-semibold">Entreprise</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link href="/a-propos" className="hover:text-foreground transition-colors">À propos</Link></li>
              <li><Link href="/blog" className="hover:text-foreground transition-colors">Blog</Link></li>
              <li><Link href="/contact" className="hover:text-foreground transition-colors">Contact</Link></li>
              <li><Link href="/legal/cgv" className="hover:text-foreground transition-colors">CGV</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="mb-4 text-sm font-semibold">Légal</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link href="/legal/mentions-legales" className="hover:text-foreground transition-colors">Mentions légales</Link></li>
              <li><Link href="/legal/privacy" className="hover:text-foreground transition-colors">Politique de confidentialité</Link></li>
              <li><Link href="/legal/rgpd" className="hover:text-foreground transition-colors">RGPD</Link></li>
              <li><Link href="/legal/cgu" className="hover:text-foreground transition-colors">CGU</Link></li>
            </ul>
          </div>
        </div>
        <div className="mt-12 border-t border-border pt-8 text-center text-sm text-muted-foreground">
          © {new Date().getFullYear()} Bapica. Tous droits réservés.
        </div>
      </div>
    </footer>
  )
}
