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
  imagesCount: number
  imagesWithoutAlt: number
  internalLinks: number
  externalLinks: number
  hreflang: boolean
  https: boolean
  responseTimeMs: number
  hasRobotsTxt: boolean
  hasSitemap: boolean
  issues: string[]
  score: number
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
    const t0 = Date.now()
    const res = await fetch(parsed.toString(), {
      redirect: 'follow',
      headers: { 'User-Agent': 'BapicaSEOBot/1.0', Accept: 'text/html' },
      signal: AbortSignal.timeout(12000),
    })
    const html = (await res.text()).slice(0, 500000)
    const responseTimeMs = Date.now() - t0

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

    // Images + attribut alt
    const imgTags = html.match(/<img\b[^>]*>/gi) || []
    const imagesCount = imgTags.length
    const imagesWithoutAlt = imgTags.filter((t) => !/\balt\s*=\s*["'][^"']*\S[^"']*["']/i.test(t)).length

    // Liens internes / externes
    const host = parsed.host
    const hrefs = [...html.matchAll(/<a\b[^>]*href=["']([^"']+)["']/gi)].map((m) => m[1])
    let internalLinks = 0, externalLinks = 0
    for (const h of hrefs) {
      if (/^https?:\/\//i.test(h)) { try { (new URL(h).host === host ? internalLinks++ : externalLinks++) } catch { /* ignore */ } }
      else if (h.startsWith('/') || h.startsWith('#') || h.startsWith('./')) internalLinks++
    }
    const hreflang = /<link[^>]*rel=["']alternate["'][^>]*hreflang=/i.test(html)
    const https = parsed.protocol === 'https:'

    // robots.txt + sitemap.xml (requêtes séparées, tolérantes)
    const origin = `${parsed.protocol}//${parsed.host}`
    const head = async (p: string) => {
      try {
        const r = await fetch(origin + p, { method: 'GET', headers: { 'User-Agent': 'BapicaSEOBot/1.0' }, signal: AbortSignal.timeout(6000) })
        return r.ok
      } catch { return false }
    }
    const [hasRobotsTxt, hasSitemap] = await Promise.all([head('/robots.txt'), head('/sitemap.xml')])

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
    if (!https) issues.push('Le site n’est pas en HTTPS.')
    if (wordCount < 300) issues.push(`Contenu mince (${wordCount} mots) — viser 600+ pour un contenu de fond.`)
    if (imagesCount > 0 && imagesWithoutAlt > 0) issues.push(`${imagesWithoutAlt}/${imagesCount} image(s) sans attribut alt.`)
    if (internalLinks < 3) issues.push(`Peu de liens internes (${internalLinks}) — renforcer le maillage.`)
    if (!hasSitemap) issues.push('sitemap.xml introuvable.')
    if (!hasRobotsTxt) issues.push('robots.txt introuvable.')
    if (responseTimeMs > 2500) issues.push(`Page lente (${responseTimeMs} ms) — optimiser la vitesse.`)

    // Score sur 100 : 100 − 6 points par problème détecté (borné à 0).
    const score = Math.max(0, 100 - issues.length * 6)

    return {
      ok: true,
      audit: {
        url: parsed.toString(), status: res.status,
        title, titleLength: title?.length || 0,
        metaDescription, metaDescriptionLength: metaDescription?.length || 0,
        canonical, robots, lang, viewport,
        h1, h2Count, ogTitle, ogDescription, ogImage, hasStructuredData,
        wordCount, imagesCount, imagesWithoutAlt, internalLinks, externalLinks,
        hreflang, https, responseTimeMs, hasRobotsTxt, hasSitemap,
        issues, score,
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
    "H1/H2, canonique, Open Graph, données structurées, nombre de mots, images sans alt, liens internes/" +
    "externes, hreflang, HTTPS, temps de réponse, présence de robots.txt et sitemap.xml, un SCORE /100 et " +
    "la liste des problèmes. Utilise-le pour auditer le site du client OU d'un concurrent AVANT de recommander.",
  input_schema: {
    type: 'object' as const,
    properties: {
      url: { type: 'string', description: 'URL de la page à auditer (ex : https://exemple.com)' },
    },
    required: ['url'],
  },
}
