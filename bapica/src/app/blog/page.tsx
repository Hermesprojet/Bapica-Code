import type { Metadata } from "next"
import Link from "next/link"

export const metadata: Metadata = {
  title: "Blog Bapica — IA et automatisation pour PME",
  description: "Conseils, comparatifs et guides sur l'IA et l'automatisation pour les PME et indépendants.",
}

const articles = [
  {
    title: "Limova vs Bapica — Quel agent IA choisir en 2026 ?",
    slug: "limova-vs-bapica",
    excerpt: "Comparatif complet entre les deux principales plateformes françaises d'agents IA.",
    date: "8 juillet 2026",
  },
]

export default function BlogPage() {
  return (
    <main className="min-h-screen bg-background py-16">
      <div className="mx-auto max-w-3xl px-4">
        <h1 className="mb-8 text-4xl font-bold">Blog Bapica</h1>
        <p className="mb-10 text-muted-foreground">
          Conseils, comparatifs et guides sur l'IA et l'automatisation pour dirigeants de PME.
        </p>
        <div className="space-y-8">
          {articles.map((article) => (
            <article key={article.slug} className="border-b border-border pb-8">
              <time className="text-sm text-muted-foreground">{article.date}</time>
              <h2 className="mt-1 text-2xl font-semibold">
                <Link href={`/blog/${article.slug}`} className="hover:underline">
                  {article.title}
                </Link>
              </h2>
              <p className="mt-2 text-muted-foreground">{article.excerpt}</p>
            </article>
          ))}
        </div>
      </div>
    </main>
  )
}
