import Link from "next/link"
import { ArrowLeft } from "lucide-react"
import { PublicPage } from "@/components/pages/public-page"

export function LegalShell({
  title,
  subtitle,
  updated,
  children,
}: {
  title: string
  subtitle?: string
  updated?: string
  children: React.ReactNode
}) {
  return (
    <PublicPage>
      <section className="relative overflow-hidden border-b border-border">
        <div className="absolute inset-0 bg-grid opacity-40" />
        <div className="absolute left-1/2 top-[-40%] h-[420px] w-[640px] -translate-x-1/2 rounded-full bg-primary/10 blur-[130px]" />
        <div className="container relative mx-auto max-w-3xl px-4 py-16 md:py-20">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Retour à l&apos;accueil
          </Link>
          <h1 className="mt-6 text-3xl font-bold tracking-tight sm:text-4xl">
            {title}
          </h1>
          {subtitle && (
            <p className="mt-3 text-lg text-muted-foreground">{subtitle}</p>
          )}
          {updated && (
            <p className="mt-4 text-xs text-muted-foreground">
              Dernière mise à jour : {updated}
            </p>
          )}
        </div>
      </section>
      <section className="container mx-auto max-w-3xl px-4 py-12 md:py-16">
        <div className="space-y-10">{children}</div>
      </section>
    </PublicPage>
  )
}

export function LegalSection({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section>
      <h2 className="mb-3 text-xl font-semibold text-foreground">{title}</h2>
      <div className="space-y-3 text-sm leading-relaxed text-muted-foreground">
        {children}
      </div>
    </section>
  )
}
