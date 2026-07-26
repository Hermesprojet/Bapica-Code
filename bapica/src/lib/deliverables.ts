/**
 * Livrables — transforme les réponses IA en documents exploitables
 */

export function generatePDF(content: string, title: string): string {
  const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${title}</title>
<style>body{font-family:Inter,sans-serif;max-width:800px;margin:40px auto;color:#f5f5f7;background:#0d0d1a;padding:20px}
h1{color:#0082e6}h2{color:#2dd4bf;margin-top:24px}ul{padding-left:20px}li{margin:6px 0}
.footer{margin-top:40px;padding-top:20px;border-top:1px solid rgba(255,255,255,0.1);color:#888;font-size:12px}
</style></head><body>${content}<div class="footer">Généré par Bapica — ${new Date().toLocaleDateString('fr')}</div></body></html>`
  return html
}

export function formatEmail(to: string, subject: string, body: string): string {
  return `To: ${to}\nSubject: ${subject}\n\n${body}\n\n---\nEnvoyé via Bapica`
}

export function formatDevis(client: string, items: { description: string; price: number }[]): string {
  const total = items.reduce((s, i) => s + i.price, 0)
  const lines = items.map(i => `| ${i.description} | ${i.price.toFixed(2)} € |`).join('\n')
  return `# Devis — ${client}\n\nDate: ${new Date().toLocaleDateString('fr')}\n\n| Prestation | Prix |\n|---|---|\n${lines}\n| **Total** | **${total.toFixed(2)} €** |\n\nValidité: 30 jours`
}

export function formatRapport(title: string, sections: { heading: string; content: string }[]): string {
  return `# ${title}\n\n${sections.map(s => `## ${s.heading}\n\n${s.content}`).join('\n\n')}`
}

// ─── Générateur de fichiers réels téléchargeables ────────────────────────────
// Produit des documents exploitables SANS dépendance binaire : CSV (ouvrable Excel),
// HTML imprimable clair (Enregistrer en PDF), Markdown, texte.

export type DeliverableKind = 'pdf' | 'excel' | 'csv' | 'markdown' | 'text' | 'word' | 'powerpoint'

// MIME des formats binaires (stockés en base64, décodés au téléchargement).
const WORD_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
const PPTX_MIME = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
export function isBinaryDeliverableMime(mime: string): boolean {
  return mime === WORD_MIME || mime === PPTX_MIME
}

export interface DeliverableSpec {
  kind: DeliverableKind
  title: string
  /** Corps en Markdown/texte (pour pdf, markdown, text). */
  content?: string
  /** En-têtes de colonnes (pour excel/csv). */
  columns?: string[]
  /** Lignes de données (pour excel/csv). */
  rows?: (string | number)[][]
}

function slugify(s: string): string {
  return (s || 'document')
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
    .slice(0, 60) || 'document'
}

function csvCell(v: string | number): string {
  const s = String(v ?? '')
  return /[",\r\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/** Conversion Markdown → HTML légère (titres, gras, listes, tableaux à pipes, paragraphes). */
function mdToHtml(md: string): string {
  const lines = (md || '').replace(/\r\n/g, '\n').split('\n')
  const out: string[] = []
  let i = 0
  const inline = (t: string) => escapeHtml(t).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  while (i < lines.length) {
    const line = lines[i]
    const h = /^(#{1,4})\s+(.*)$/.exec(line)
    if (h) { const n = h[1].length; out.push(`<h${n}>${inline(h[2])}</h${n}>`); i++; continue }
    // Tableau à pipes : ligne d'en-tête + séparateur |---|
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
      const cells = (row: string) => row.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim())
      const head = cells(line)
      i += 2
      const body: string[][] = []
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) { body.push(cells(lines[i])); i++ }
      out.push(
        '<table><thead><tr>' + head.map((c) => `<th>${inline(c)}</th>`).join('') + '</tr></thead><tbody>' +
        body.map((r) => '<tr>' + r.map((c) => `<td>${inline(c)}</td>`).join('') + '</tr>').join('') +
        '</tbody></table>'
      )
      continue
    }
    // Liste à puces
    if (/^\s*[-*]\s+/.test(line)) {
      const items: string[] = []
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) { items.push(`<li>${inline(lines[i].replace(/^\s*[-*]\s+/, ''))}</li>`); i++ }
      out.push(`<ul>${items.join('')}</ul>`)
      continue
    }
    if (line.trim() === '') { i++; continue }
    out.push(`<p>${inline(line)}</p>`)
    i++
  }
  return out.join('\n')
}

/** HTML clair prêt à imprimer / « Enregistrer au format PDF ». */
export function printableHtml(title: string, markdown: string): string {
  return `<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escapeHtml(title)}</title>
<style>
  :root{color-scheme:light}
  body{font-family:-apple-system,Segoe UI,Inter,sans-serif;max-width:800px;margin:40px auto;color:#111827;background:#fff;padding:24px;line-height:1.55}
  h1{color:#111827;font-size:26px;margin:0 0 16px} h2{color:#2563EB;font-size:19px;margin:24px 0 8px} h3,h4{color:#111827;margin:18px 0 6px}
  table{border-collapse:collapse;width:100%;margin:14px 0} th,td{border:1px solid #e5e7eb;padding:8px 10px;text-align:left;font-size:14px} th{background:#f9fafb}
  ul{padding-left:20px} li{margin:4px 0} p{margin:8px 0}
  .footer{margin-top:40px;padding-top:16px;border-top:1px solid #e5e7eb;color:#6b7280;font-size:12px}
  @media print{body{margin:0}}
</style></head><body>
${mdToHtml(markdown)}
<div class="footer">Généré par Bapica — ${new Date().toLocaleDateString('fr')}. Pour un PDF : menu d'impression → « Enregistrer au format PDF ».</div>
</body></html>`
}

/** Construit le fichier téléchargeable (mime, nom, contenu) à partir d'une spécification. */
export function buildDeliverable(spec: DeliverableSpec): { mime: string; filename: string; content: string } {
  const base = slugify(spec.title)
  switch (spec.kind) {
    case 'excel':
    case 'csv': {
      const cols = spec.columns || []
      const rows = spec.rows || []
      const toLine = (arr: (string | number)[]) => arr.map(csvCell).join(',')
      const csv = [toLine(cols), ...rows.map(toLine)].filter((l) => l.length).join('\r\n')
      // BOM UTF-8 pour qu'Excel affiche correctement les accents.
      return { mime: 'text/csv;charset=utf-8', filename: `${base}.csv`, content: '﻿' + csv }
    }
    case 'pdf':
      return { mime: 'text/html;charset=utf-8', filename: `${base}.html`, content: printableHtml(spec.title, spec.content || '') }
    case 'markdown':
      return { mime: 'text/markdown;charset=utf-8', filename: `${base}.md`, content: spec.content || '' }
    case 'text':
    default:
      return { mime: 'text/plain;charset=utf-8', filename: `${base}.txt`, content: spec.content || '' }
  }
}

// ─── Vrais fichiers Office (.docx / .pptx) — libs pur-JS, import paresseux ────

type MdBlock =
  | { type: 'heading'; level: number; text: string }
  | { type: 'bullets'; items: string[] }
  | { type: 'table'; head: string[]; rows: string[][] }
  | { type: 'paragraph'; text: string }

/** Parse un Markdown léger en blocs structurés (titres, listes, tableaux, paragraphes). */
function parseMarkdownBlocks(md: string): MdBlock[] {
  const lines = (md || '').replace(/\r\n/g, '\n').split('\n')
  const out: MdBlock[] = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    const h = /^(#{1,4})\s+(.*)$/.exec(line)
    if (h) { out.push({ type: 'heading', level: h[1].length, text: h[2].trim() }); i++; continue }
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
      const cells = (row: string) => row.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim())
      const head = cells(line)
      i += 2
      const rows: string[][] = []
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) { rows.push(cells(lines[i])); i++ }
      out.push({ type: 'table', head, rows })
      continue
    }
    if (/^\s*[-*]\s+/.test(line)) {
      const items: string[] = []
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) { items.push(lines[i].replace(/^\s*[-*]\s+/, '').trim()); i++ }
      out.push({ type: 'bullets', items })
      continue
    }
    if (line.trim() === '') { i++; continue }
    out.push({ type: 'paragraph', text: line.trim() })
    i++
  }
  return out
}

/** Découpe une chaîne en segments gras/normal à partir des **…**. */
function splitBold(text: string): { text: string; bold: boolean }[] {
  const parts: { text: string; bold: boolean }[] = []
  const re = /\*\*(.+?)\*\*/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push({ text: text.slice(last, m.index), bold: false })
    parts.push({ text: m[1], bold: true })
    last = m.index + m[0].length
  }
  if (last < text.length) parts.push({ text: text.slice(last), bold: false })
  return parts.length ? parts : [{ text, bold: false }]
}

/** Retire le balisage Markdown inline (gras) pour un rendu texte simple. */
function stripInline(text: string): string {
  return text.replace(/\*\*(.+?)\*\*/g, '$1').replace(/^#{1,4}\s+/, '')
}

/** Génère un vrai document Word (.docx) à partir d'un Markdown, en base64. */
async function buildWordBase64(title: string, markdown: string): Promise<string> {
  const docx = await import('docx')
  const { Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType } = docx
  const headingFor = (level: number) =>
    level <= 1 ? HeadingLevel.HEADING_1 : level === 2 ? HeadingLevel.HEADING_2 : level === 3 ? HeadingLevel.HEADING_3 : HeadingLevel.HEADING_4
  const runs = (text: string) => splitBold(text).map((s) => new TextRun({ text: s.text, bold: s.bold }))

  const children: (InstanceType<typeof Paragraph> | InstanceType<typeof Table>)[] = [
    new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun({ text: title })] }),
  ]
  for (const b of parseMarkdownBlocks(markdown)) {
    if (b.type === 'heading') {
      children.push(new Paragraph({ heading: headingFor(b.level), children: runs(b.text) }))
    } else if (b.type === 'bullets') {
      for (const it of b.items) children.push(new Paragraph({ bullet: { level: 0 }, children: runs(it) }))
    } else if (b.type === 'paragraph') {
      children.push(new Paragraph({ children: runs(b.text) }))
    } else if (b.type === 'table') {
      const headerRow = new TableRow({
        children: b.head.map((c) => new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: c, bold: true })] })] })),
      })
      const bodyRows = b.rows.map(
        (r) => new TableRow({ children: r.map((c) => new TableCell({ children: [new Paragraph({ children: runs(c) })] })) }),
      )
      children.push(new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, rows: [headerRow, ...bodyRows] }))
    }
  }

  const doc = new Document({ sections: [{ children }] })
  const buf = await Packer.toBuffer(doc)
  return Buffer.from(buf).toString('base64')
}

/** Génère une vraie présentation PowerPoint (.pptx) à partir d'un Markdown, en base64.
 *  Chaque titre Markdown (# / ##) démarre une nouvelle diapositive ; les lignes suivantes
 *  deviennent des puces. Sans titre, une seule diapositive reprend le titre du document. */
async function buildPptxBase64(title: string, markdown: string): Promise<string> {
  const mod = await import('pptxgenjs')
  const Pptx = (mod as unknown as { default: new () => PptxInstance }).default
  const pptx = new Pptx()

  type SlideSpec = { title: string; bullets: string[] }
  const slides: SlideSpec[] = []
  let current: SlideSpec | null = null
  for (const b of parseMarkdownBlocks(markdown)) {
    if (b.type === 'heading' && b.level <= 2) {
      current = { title: b.text, bullets: [] }
      slides.push(current)
    } else if (b.type === 'bullets') {
      if (!current) { current = { title, bullets: [] }; slides.push(current) }
      current.bullets.push(...b.items.map(stripInline))
    } else if (b.type === 'paragraph') {
      if (!current) { current = { title, bullets: [] }; slides.push(current) }
      current.bullets.push(stripInline(b.text))
    } else if (b.type === 'heading') {
      if (!current) { current = { title, bullets: [] }; slides.push(current) }
      current.bullets.push(stripInline(b.text))
    } else if (b.type === 'table') {
      if (!current) { current = { title, bullets: [] }; slides.push(current) }
      current.bullets.push([b.head.join(' | '), ...b.rows.map((r) => r.join(' | '))].join('\n'))
    }
  }
  if (!slides.length) slides.push({ title, bullets: [] })

  for (const s of slides) {
    const slide = pptx.addSlide()
    slide.addText(s.title || title, { x: 0.5, y: 0.3, w: 9, h: 0.8, fontSize: 26, bold: true, color: '2563EB' })
    if (s.bullets.length) {
      slide.addText(
        s.bullets.map((t) => ({ text: t, options: { bullet: true, fontSize: 16, color: '111827' } })),
        { x: 0.6, y: 1.3, w: 8.8, h: 5 },
      )
    }
  }

  return (await pptx.write({ outputType: 'base64' })) as string
}

// Type minimal de l'instance pptxgenjs utilisée (évite un any global).
interface PptxInstance {
  addSlide(): { addText(text: unknown, opts: Record<string, unknown>): void }
  write(opts: { outputType: string }): Promise<string | ArrayBuffer | Uint8Array>
}

/** Construit le fichier livrable, y compris les formats binaires Office (base64). */
export async function buildDeliverableFile(
  spec: DeliverableSpec,
): Promise<{ mime: string; filename: string; content: string; base64: boolean }> {
  const base = slugify(spec.title)
  if (spec.kind === 'word') {
    return { mime: WORD_MIME, filename: `${base}.docx`, content: await buildWordBase64(spec.title, spec.content || ''), base64: true }
  }
  if (spec.kind === 'powerpoint') {
    return { mime: PPTX_MIME, filename: `${base}.pptx`, content: await buildPptxBase64(spec.title, spec.content || ''), base64: true }
  }
  const f = buildDeliverable(spec)
  return { ...f, base64: false }
}
