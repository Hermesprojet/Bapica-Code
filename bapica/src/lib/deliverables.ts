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
