/**
 * Audit SEO réel : récupère une page et en extrait les signaux SEO (titre, meta,
 * balises, Open Graph, données structurées…). Lecture seule, sans dépendance externe
 * (extraction par regex, pas de cheerio).
 */

function meta(html: string, attr: 'name' | 'property', key: string): string | null {
  const re = new RegExp(`<meta[^>]*${attr}=["']${key}["'][^>]*content=["']([^"']*)["']`, 'i')
  const re2 = new RegExp(`<meta[^>]*content=["']([^"']*)["'][^>]*${attr}=["']${key}["']`, 'i')
  return (html.match(re)?.[1] ?? html.match(re2)?.[1] ?? null)?.trim() || null
}

function allTags(html: string, tag: string): string[] {
  const out: string[] = []
  const re = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`, 'gi')
  let m: RegExpExecArray | null
  while ((m = re.exec(html))) {
    const text = m[1].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
    if (text) out.push(text.slice(0, 160))
  }
  return out
}

export interface SeoAudit {
  url: string
  status: number
  title: string | null
  titleLength: number
  metaDescription: string | null
  metaDescriptionLength: number
  canonical: string | null
  robots: string | null
  lang: string | null
  viewport: boolean
  h1: string[]
  h2Count: number
  ogTitle: string | null
  ogDescription: string | null
  ogImage: boolean
  hasStructuredData: boolean
  wordCount: number
  issues: string[]
}

export async function auditSite(inputUrl: string): Promise<{ ok: boolean; audit?: SeoAudit; error?: string }> {
  let url = inputUrl.trim()
  if (!/^https?:\/\//i.test(url)) url = `https://${url}`
  let parsed: URL
  try { parsed = new URL(url) } catch { return { ok: false, error: 'URL invalide.' } }
  if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') {
    return { ok: false, error: 'Seuls http(s) sont autorisés.' }
  }

  try {
    const res = await fetch(parsed.toString(), {
      redirect: 'follow',
      headers: { 'User-Agent': 'BapicaSEOBot/1.0', Accept: 'text/html' },
      signal: AbortSignal.timeout(12000),
    })
    const html = (await res.text()).slice(0, 500000)

    const title = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1]?.replace(/\s+/g, ' ').trim() || null
    const metaDescription = meta(html, 'name', 'description')
    const canonical = html.match(/<link[^>]*rel=["']canonical["'][^>]*href=["']([^"']*)["']/i)?.[1] || null
    const robots = meta(html, 'name', 'robots')
    const lang = html.match(/<html[^>]*lang=["']([^"']*)["']/i)?.[1] || null
    const viewport = /<meta[^>]*name=["']viewport["']/i.test(html)
    const h1 = allTags(html, 'h1')
    const h2Count = (html.match(/<h2[^>]*>/gi) || []).length
    const ogTitle = meta(html, 'property', 'og:title')
    const ogDescription = meta(html, 'property', 'og:description')
    const ogImage = Boolean(meta(html, 'property', 'og:image'))
    const hasStructuredData = /application\/ld\+json/i.test(html)

    const bodyText = html
      .replace(/<script[\s\S]*?<\/script>/gi, ' ')
      .replace(/<style[\s\S]*?<\/style>/gi, ' ')
      .replace(/<[^>]+>/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
    const wordCount = bodyText ? bodyText.split(' ').length : 0

    const issues: string[] = []
    if (!title) issues.push('Balise <title> absente.')
    else if (title.length < 30) issues.push(`Titre court (${title.length} caractères) — viser 50-60.`)
    else if (title.length > 65) issues.push(`Titre long (${title.length} caractères) — risque de troncature.`)
    if (!metaDescription) issues.push('Meta description absente.')
    else if (metaDescription.length < 70 || metaDescription.length > 160) issues.push(`Meta description à ${metaDescription.length} caractères — viser 140-160.`)
    if (h1.length === 0) issues.push('Aucun <h1>.')
    else if (h1.length > 1) issues.push(`${h1.length} balises <h1> — n'en garder qu'une.`)
    if (!canonical) issues.push('URL canonique absente.')
    if (!viewport) issues.push('Balise viewport absente (mobile).')
    if (!lang) issues.push('Attribut lang absent sur <html>.')
    if (!ogTitle && !ogDescription) issues.push('Balises Open Graph absentes (partage réseaux).')
    if (!hasStructuredData) issues.push('Aucune donnée structurée (JSON-LD).')
    if (robots && /noindex/i.test(robots)) issues.push('La page est en noindex (non indexable).')

    return {
      ok: true,
      audit: {
        url: parsed.toString(), status: res.status,
        title, titleLength: title?.length || 0,
        metaDescription, metaDescriptionLength: metaDescription?.length || 0,
        canonical, robots, lang, viewport,
        h1, h2Count, ogTitle, ogDescription, ogImage, hasStructuredData,
        wordCount, issues,
      },
    }
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e)
    return { ok: false, error: msg.includes('timeout') ? 'Le site n’a pas répondu à temps.' : msg }
  }
}

export const auditSiteTool = {
  name: 'auditer_site',
  description:
    "Analyse RÉELLE d'une page web pour le SEO : récupère la page et renvoie titre, meta description, " +
    "H1/H2, canonique, Open Graph, données structurées, nombre de mots et une liste de problèmes détectés. " +
    "Utilise-le pour auditer le site du client ou d'un concurrent AVANT de proposer des recommandations.",
  input_schema: {
    type: 'object' as const,
    properties: {
      url: { type: 'string', description: 'URL de la page à auditer (ex : https://exemple.com)' },
    },
    required: ['url'],
  },
}
