import Link from "next/link"

export function Footer() {
  return (
    <footer className="border-t border-border py-12">
      <div className="container mx-auto px-4">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground font-bold text-sm">
                B
              </div>
              <span className="text-lg font-bold">Bapica</span>
            </div>
            <p className="mt-4 text-sm text-muted-foreground">
              Plateforme multi-agents IA pour PME et indépendants.
            </p>
          </div>
          <div>
            <h4 className="mb-4 text-sm font-semibold">Agents</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link href="#" className="hover:text-foreground transition-colors">Prospecteur</Link></li>
              <li><Link href="#" className="hover:text-foreground transition-colors">Support Client</Link></li>
              <li><Link href="#" className="hover:text-foreground transition-colors">Agent Téléphonique</Link></li>
              <li><Link href="#" className="hover:text-foreground transition-colors">Créateur de Contenu</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="mb-4 text-sm font-semibold">Entreprise</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link href="#" className="hover:text-foreground transition-colors">À propos</Link></li>
              <li><Link href="#" className="hover:text-foreground transition-colors">Blog</Link></li>
              <li><Link href="#" className="hover:text-foreground transition-colors">Contact</Link></li>
              <li><Link href="#" className="hover:text-foreground transition-colors">CGV</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="mb-4 text-sm font-semibold">Légal</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link href="#" className="hover:text-foreground transition-colors">Mentions légales</Link></li>
              <li><Link href="#" className="hover:text-foreground transition-colors">Politique de confidentialité</Link></li>
              <li><Link href="#" className="hover:text-foreground transition-colors">RGPD</Link></li>
              <li><Link href="#" className="hover:text-foreground transition-colors">CGU</Link></li>
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
