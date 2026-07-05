'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Menu, X } from 'lucide-react'

export function Navbar() {
  const [open, setOpen] = useState(false)

  const navLinks = [
    { href: '#features', label: 'Fonctionnalités' },
    { href: '#use-cases', label: "Cas d'usage" },
    { href: '#agents', label: 'Agents' },
    { href: '#pricing', label: 'Tarifs' },
  ]

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-md border-b border-border">
      <div className="container mx-auto max-w-6xl flex h-14 sm:h-16 items-center justify-between px-4">
        {/* Logo */}
        <Link href="/" className="text-lg sm:text-xl font-bold tracking-tight text-foreground shrink-0">
          Bapica
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden md:flex items-center gap-6 lg:gap-8 text-sm text-muted-foreground">
          {navLinks.map(l => (
            <Link key={l.href} href={l.href} className="hover:text-foreground transition-colors">
              {l.label}
            </Link>
          ))}
        </nav>

        {/* Desktop CTA */}
        <div className="hidden md:flex items-center gap-3 lg:gap-4">
          <Link href="/login" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
            Se connecter
          </Link>
          <Link href="/signup" className="bg-foreground text-background rounded-lg px-3 lg:px-4 py-2 text-sm font-medium hover:bg-foreground/90 transition-all">
            Essayer gratuitement
          </Link>
        </div>

        {/* Mobile hamburger */}
        <button
          onClick={() => setOpen(!open)}
          className="md:hidden p-2 -mr-2 text-foreground hover:text-muted-foreground transition-colors"
          aria-label="Menu"
        >
          {open ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </div>

      {/* Mobile menu */}
      {open && (
        <div className="md:hidden border-t border-border bg-background animate-fade-in">
          <nav className="container px-4 py-4 flex flex-col gap-1">
            {navLinks.map(l => (
              <Link
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className="px-4 py-3 text-base text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors"
              >
                {l.label}
              </Link>
            ))}
            <hr className="my-2 border-border" />
            <Link
              href="/login"
              onClick={() => setOpen(false)}
              className="px-4 py-3 text-base text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors"
            >
              Se connecter
            </Link>
            <Link
              href="/signup"
              onClick={() => setOpen(false)}
              className="mt-2 bg-foreground text-background rounded-lg px-4 py-3 text-base font-medium text-center hover:bg-foreground/90 transition-all"
            >
              Essayer gratuitement
            </Link>
          </nav>
        </div>
      )}
    </header>
  )
}
