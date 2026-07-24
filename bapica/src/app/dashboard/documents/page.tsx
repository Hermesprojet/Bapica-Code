'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { FileText, FileSpreadsheet, Download, Trash2, Loader2, AlertCircle, ExternalLink } from 'lucide-react'

interface DocRow {
  id: string
  agent_id: string | null
  kind: string
  title: string
  filename: string
  mime: string
  created_at: string
}

const KIND_LABEL: Record<string, string> = {
  pdf: 'PDF (imprimable)', excel: 'Tableau (Excel/CSV)', csv: 'CSV', markdown: 'Markdown', text: 'Texte',
}

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocRow[]>([])
  const [loading, setLoading] = useState(true)
  const [needsSetup, setNeedsSetup] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const token = async () => (await supabase.auth.getSession()).data.session?.access_token || ''

  const load = async () => {
    try {
      const res = await fetch('/api/deliverables', { headers: { Authorization: `Bearer ${await token()}` } })
      const data = await res.json()
      if (res.ok) { setDocs(data.documents || []); setNeedsSetup(Boolean(data.needsSetup)) }
    } catch { /* ignore */ }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const download = async (d: DocRow) => {
    setBusy(d.id); setNotice(null)
    try {
      const res = await fetch(`/api/deliverables/${d.id}`, { headers: { Authorization: `Bearer ${await token()}` } })
      if (!res.ok) { setNotice('Téléchargement impossible.'); setBusy(null); return }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = d.filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch { setNotice('Erreur de connexion.') }
    setBusy(null)
  }

  const exportGoogle = async (d: DocRow) => {
    setBusy(d.id); setNotice(null)
    try {
      const res = await fetch(`/api/deliverables/${d.id}/google`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${await token()}` },
      })
      const data = await res.json()
      if (res.ok && data.success && data.url) {
        window.open(data.url, '_blank', 'noopener')
        setNotice(data.target === 'sheet' ? 'Exporté vers Google Sheets.' : 'Exporté vers Google Docs.')
      } else {
        setNotice(data.error || 'Export impossible.')
      }
    } catch { setNotice('Erreur de connexion.') }
    setBusy(null)
  }

  const remove = async (id: string) => {
    setBusy(id)
    try {
      await fetch('/api/deliverables', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
        body: JSON.stringify({ id }),
      })
    } catch { /* ignore */ }
    setBusy(null)
    load()
  }

  return (
    <div>
      <div className="reveal mb-6">
        <h1 className="text-2xl font-bold">Documents</h1>
        <p className="mt-1 text-muted-foreground">
          Les fichiers produits par vos agents (devis, rapports, tableaux) — prêts à télécharger.
          Demandez par exemple à Léo « prépare un devis PDF pour… » ou « un tableau Excel de… ».
        </p>
      </div>

      {notice && (
        <div className="mb-6 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{notice}</div>
      )}

      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
      ) : needsSetup ? (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-5 text-sm">
          <div className="flex items-center gap-2 font-semibold text-amber-700"><AlertCircle className="h-4 w-4" /> Base non initialisée</div>
          <p className="mt-2 text-muted-foreground">
            La table <code className="rounded bg-muted px-1">deliverables</code> est absente : exécutez tout
            le contenu de <code className="rounded bg-muted px-1">bapica/supabase-schema.sql</code> dans Supabase → SQL Editor.
          </p>
        </div>
      ) : docs.length === 0 ? (
        <div className="card-professional flex items-center gap-3 p-6 text-sm text-muted-foreground">
          <FileText className="h-5 w-5 text-primary" />
          Aucun document pour l&apos;instant. Demandez à un agent d&apos;en produire un.
        </div>
      ) : (
        <div className="space-y-2">
          {docs.map((d) => {
            const isTable = d.kind === 'excel' || d.kind === 'csv'
            const Icon = isTable ? FileSpreadsheet : FileText
            return (
              <div key={d.id} className="card-professional flex items-center justify-between gap-3 p-4">
                <div className="flex min-w-0 items-center gap-3">
                  <Icon className="h-5 w-5 shrink-0 text-primary" />
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium">{d.title}</div>
                    <div className="text-[11px] text-muted-foreground">
                      {KIND_LABEL[d.kind] || d.kind}
                      {d.agent_id ? ` · ${d.agent_id}` : ''} · {new Date(d.created_at).toLocaleDateString('fr')}
                    </div>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <button
                    onClick={() => exportGoogle(d)}
                    disabled={busy === d.id}
                    title={isTable ? 'Créer un Google Sheet' : 'Créer un Google Doc'}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs font-medium hover:bg-muted disabled:opacity-50"
                  >
                    <ExternalLink className="h-3.5 w-3.5" /> Google
                  </button>
                  <button
                    onClick={() => download(d)}
                    disabled={busy === d.id}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                  >
                    {busy === d.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
                    Télécharger
                  </button>
                  <button onClick={() => remove(d.id)} disabled={busy === d.id} className="text-muted-foreground hover:text-destructive transition-colors" aria-label="Supprimer">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
