import Anthropic from '@anthropic-ai/sdk'

// Recherche internet sur l'entreprise du client : lit le site web + recherche
// web (SerpAPI si clé), puis résume avec Claude en un profil factuel.
// ÉCRIT À L'AVEUGLE (non testable en sandbox : réseau bloqué + pas de clés).
// Clés prod : ANTHROPIC_API_KEY (résumé), SERPAPI_KEY (recherche, optionnelle).

// Récupère le texte lisible d'une page web (HTML nettoyé, tronqué).
export async function fetchWebsiteText(url: string): Promise<string> {
  let target = url.trim()
  if (!/^https?:\/\//i.test(target)) target = `https://${target}`
  try {
    const res = await fetch(target, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; BapicaBot/1.0)' },
      redirect: 'follow',
      signal: AbortSignal.timeout(12000),
    })
    if (!res.ok) return ''
    const html = await res.text()
    return html
      .replace(/<script[\s\S]*?<\/script>/gi, ' ')
      .replace(/<style[\s\S]*?<\/style>/gi, ' ')
      .replace(/<[^>]+>/g, ' ')
      .replace(/&[a-z]+;/gi, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .slice(0, 6000)
  } catch {
    return ''
  }
}

// Recherche web via SerpAPI (Google). [] si pas de clé.
export async function webSearch(query: string): Promise<{ title: string; snippet: string; link: string }[]> {
  const key = process.env.SERPAPI_KEY
  if (!key) return []
  try {
    const res = await fetch(
      `https://serpapi.com/search.json?engine=google&num=6&q=${encodeURIComponent(query)}&api_key=${key}`,
      { signal: AbortSignal.timeout(12000) }
    )
    const data = await res.json()
    return (data.organic_results || [])
      .slice(0, 6)
      .map((r: any) => ({ title: r.title || '', snippet: r.snippet || '', link: r.link || '' }))
  } catch {
    return []
  }
}

export interface ResearchInput {
  companyName: string
  website?: string
  sector?: string
  city?: string
  country?: string
}

// Rassemble les sources et fait rédiger un profil factuel par Claude.
export async function researchCompany(input: ResearchInput): Promise<{ summary: string; sources: string[] }> {
  const apiKey = process.env.ANTHROPIC_API_KEY
  if (!apiKey) throw new Error("Résumé indisponible (clé API manquante).")

  const sources: string[] = []
  const blocks: string[] = []

  if (input.website) {
    const siteText = await fetchWebsiteText(input.website)
    if (siteText) { blocks.push(`SITE WEB (${input.website}) :\n${siteText}`); sources.push(input.website) }
  }

  const query = [input.companyName, input.city, input.sector].filter(Boolean).join(' ')
  const results = await webSearch(query)
  if (results.length) {
    blocks.push('RÉSULTATS DE RECHERCHE WEB :\n' + results.map((r) => `- ${r.title} — ${r.snippet} (${r.link})`).join('\n'))
    results.forEach((r) => r.link && sources.push(r.link))
  }

  if (blocks.length === 0) {
    throw new Error("Aucune source trouvée. Renseignez un site web dans votre profil, ou configurez la recherche web (SERPAPI_KEY).")
  }

  const client = new Anthropic({ apiKey, timeout: 40000 })
  const completion = await client.messages.create({
    model: 'claude-sonnet-4-5',
    max_tokens: 1200,
    system:
      "Tu es analyste. À partir d'extraits web BRUTS concernant une entreprise, rédige un PROFIL FACTUEL en français, utile pour conseiller cette entreprise. Structure : activité et offre, positionnement, clientèle, taille/implantation, présence en ligne, concurrents visibles, signaux notables. N'INVENTE RIEN : si une info n'est pas dans les extraits, ne la mentionne pas. Pas de blabla, du concret. 200-350 mots.",
    messages: [{
      role: 'user',
      content: `Entreprise : ${input.companyName}${input.city ? ' — ' + input.city : ''}${input.country ? ', ' + input.country : ''}\nSecteur déclaré : ${input.sector || 'non précisé'}\n\n${blocks.join('\n\n')}`,
    }],
  })

  const summary = completion.content.filter((b: any) => b.type === 'text').map((b: any) => b.text).join('\n').trim()
  return { summary, sources: [...new Set(sources)] }
}
