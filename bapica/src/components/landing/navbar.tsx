import Link from "next/link"

export function Navbar() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-md border-b border-border">
      <div className="container mx-auto max-w-6xl flex h-16 items-center justify-between px-4">
        {/* Logo */}
        <Link href="/" className="text-xl font-bold tracking-tight text-foreground">
          Bapica
        </Link>

        {/* Navigation */}
        <nav className="hidden md:flex items-center gap-8 text-sm text-muted-foreground">
          <Link href="#features" className="hover:text-foreground transition-colors">
            Fonctionnalités
          </Link>
          <Link href="#use-cases" className="hover:text-foreground transition-colors">
            Cas d&apos;usage
          </Link>
          <Link href="#agents" className="hover:text-foreground transition-colors">
            Agents
          </Link>
          <Link href="#pricing" className="hover:text-foreground transition-colors">
            Tarifs
          </Link>
        </nav>

        {/* CTA buttons */}
        <div className="flex items-center gap-4">
          <Link
            href="/login"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Se connecter
          </Link>
          <Link
            href="/signup"
            className="bg-foreground text-background rounded-lg px-4 py-2 text-sm font-medium hover:bg-foreground/90 transition-all"
          >
            Essayer gratuitement
          </Link>
        </div>
      </div>
    </header>
  )
}
