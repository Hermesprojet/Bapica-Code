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

export type DeliverableKind = 'pdf' | 'excel' | 'csv' | 'markdown' | 'text'

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
