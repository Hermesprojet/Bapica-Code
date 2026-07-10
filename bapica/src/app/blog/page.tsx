import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Blog Bapica — IA et automatisation pour PME",
  description: "Conseils et guides sur l'IA et l'automatisation pour les PME et indépendants.",
}

const articles: { title: string; slug: string; excerpt: string; date: string }[] = []

export default function BlogPage() {
  return (
    <main className="min-h-screen bg-background py-16">
      <div className="mx-auto max-w-3xl px-4">
        <h1 className="mb-8 text-4xl font-bold">Blog Bapica</h1>
        <p className="mb-10 text-muted-foreground">
          Conseils et guides sur l'IA et l'automatisation pour dirigeants de PME.
        </p>
        {articles.length === 0 ? (
          <p className="text-muted-foreground">Aucun article pour le moment. Revenez bientôt !</p>
        ) : (
          <div className="space-y-8">
            {articles.map((article) => (
              <article key={article.slug} className="border-b border-border pb-8">
                <time className="text-sm text-muted-foreground">{article.date}</time>
                <h2 className="mt-1 text-2xl font-semibold">
                  <a href={`/blog/${article.slug}`} className="hover:underline">
                    {article.title}
                  </a>
                </h2>
                <p className="mt-2 text-muted-foreground">{article.excerpt}</p>
              </article>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
