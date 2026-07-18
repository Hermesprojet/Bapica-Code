'use client'

import { useEffect, useRef, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { BookOpen, Upload, FileText, Trash2, Loader2, Plus, Sparkles, X, Globe } from 'lucide-react'

interface Doc { source: string; chunks: number }

export default function KnowledgePage() {
  const [docs, setDocs] = useState<Doc[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<{ kind: 'ok' | 'err'; msg: string } | null>(null)
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [showBanner, setShowBanner] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    try { setShowBanner(localStorage.getItem('bapica_kb_banner') !== 'off') } catch { setShowBanner(true) }
  }, [])
  const dismissBanner = () => {
    try { localStorage.setItem('bapica_kb_banner', 'off') } catch { /* ignore */ }
    setShowBanner(false)
  }

  const token = async () => (await supabase.auth.getSession()).data.session?.access_token || ''

  const load = async () => {
    try {
      const res = await fetch('/api/knowledge', { headers: { Authorization: `Bearer ${await token()}` } })
      const data = await res.json()
      if (res.ok) setDocs(data.documents || [])
    } catch { /* ignore */ }
    setLoading(false)
  }

  useEffect(() => { load() /* eslint-disable-next-line */ }, [])

  const afterUpload = (res: Response, data: any, label: string) => {
    if (res.ok && data.success) {
      setNotice({ kind: 'ok', msg: `« ${label} » ajouté (${data.chunks} extraits).` })
      setTitle(''); setText(''); if (fileRef.current) fileRef.current.value = ''
      load()
    } else {
      setNotice({ kind: 'err', msg: data.error || 'Échec de l\'ajout.' })
    }
  }

  const uploadFile = async (file: File) => {
    setBusy(true); setNotice(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch('/api/knowledge/upload', { method: 'POST', headers: { Authorization: `Bearer ${await token()}` }, body: form })
      afterUpload(res, await res.json(), file.name)
    } catch { setNotice({ kind: 'err', msg: 'Erreur de connexion.' }) }
    setBusy(false)
  }

  const uploadText = async () => {
    if (!text.trim() || busy) return
    setBusy(true); setNotice(null)
    try {
      const res = await fetch('/api/knowledge/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
        body: JSON.stringify({ title: title.trim() || 'Note', text }),
      })
      afterUpload(res, await res.json(), title.trim() || 'Note')
    } catch { setNotice({ kind: 'err', msg: 'Erreur de connexion.' }) }
    setBusy(false)
  }

  const [researching, setResearching] = useState(false)
  const [research, setResearch] = useState<string | null>(null)

  const runResearch = async () => {
    if (researching) return
    setResearching(true); setResearch(null); setNotice(null)
    try {
      const res = await fetch('/api/company/research', { method: 'POST', headers: { Authorization: `Bearer ${await token()}` } })
      const data = await res.json()
      if (res.ok && data.success) {
        setResearch(data.summary)
        if (data.stored) { setNotice({ kind: 'ok', msg: 'Profil web ajouté à vos documents.' }); load() }
      } else {
        setNotice({ kind: 'err', msg: data.error || 'Échec de la recherche.' })
      }
    } catch { setNotice({ kind: 'err', msg: 'Erreur de connexion.' }) }
    setResearching(false)
  }

  const remove = async (source: string) => {
    await fetch('/api/knowledge', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
      body: JSON.stringify({ source }),
    })
    load()
  }

  return (
    <div>
      {/* Bandeau pédagogique (pourquoi ajouter des documents) — refermable */}
      {showBanner && (
        <div className="relative mb-6 overflow-hidden rounded-2xl border border-primary/20 bg-gradient-to-br from-primary/[0.07] to-primary/[0.02] p-5 pr-12">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h2 className="font-semibold">Rendez vos agents experts de VOTRE entreprise</h2>
              <p className="mt-1 text-sm text-muted-foreground leading-relaxed">
                Ajoutez vos documents clés — catalogue, tarifs, fiches produits, procédures, présentation,
                CGV… Vos agents s&apos;en serviront pour répondre <strong className="text-foreground">avec précision et à votre place</strong>,
                au lieu de rester généralistes. Plus vous en ajoutez, plus Bapica est pertinent.
              </p>
            </div>
          </div>
          <button
            onClick={dismissBanner}
            className="absolute right-3 top-3 inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          >
            <X className="h-3.5 w-3.5" /> Ne plus afficher
          </button>
        </div>
      )}

      <div className="mb-8 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary"><BookOpen className="h-5 w-5" /></div>
        <div>
          <h1 className="text-xl font-bold">Base de connaissances</h1>
          <p className="text-sm text-muted-foreground">Ajoutez vos documents : vos agents répondront à partir de VOTRE entreprise.</p>
        </div>
      </div>

      {notice && (
        <div className={`mb-6 rounded-xl border p-4 text-sm ${notice.kind === 'ok' ? 'border-green-500/30 bg-green-500/5 text-green-700' : 'border-destructive/30 bg-destructive/5 text-destructive'}`}>
          {notice.msg}
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {/* Upload fichier */}
        <div className="card-elevated p-6">
          <h2 className="mb-3 font-semibold text-sm">Téléverser un document</h2>
          <input ref={fileRef} type="file" accept=".pdf,.docx,.txt,.md,.csv" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadFile(f) }} />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={busy}
            className="flex w-full flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border py-10 text-sm text-muted-foreground hover:border-primary/40 hover:bg-muted/40 disabled:opacity-50 transition-colors"
          >
            {busy ? <Loader2 className="h-6 w-6 animate-spin" /> : <Upload className="h-6 w-6" />}
            <span>{busy ? 'Traitement…' : 'Choisir un fichier (PDF, Word, TXT)'}</span>
          </button>
          <p className="mt-2 text-xs text-muted-foreground">PDF, DOCX, TXT, MD, CSV — max 8 Mo.</p>
        </div>

        {/* Coller du texte */}
        <div className="card-elevated p-6">
          <h2 className="mb-3 font-semibold text-sm">Ou coller du texte</h2>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Titre (ex : Fiches produits)"
            className="mb-3 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary" />
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4} placeholder="Collez ici des infos sur votre entreprise, produits, process…"
            className="w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary" />
          <button onClick={uploadText} disabled={!text.trim() || busy}
            className="mt-3 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-all">
            <Plus className="h-4 w-4" /> Ajouter
          </button>
        </div>
      </div>

      {/* Recherche internet automatique sur l'entreprise */}
      <div className="card-professional mt-6 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary"><Globe className="h-4.5 w-4.5" /></div>
            <div>
              <div className="font-semibold text-sm">Recherche internet sur votre entreprise</div>
              <p className="text-xs text-muted-foreground">Bapica lit votre site et cherche en ligne pour rédiger un profil de votre société.</p>
            </div>
          </div>
          <button onClick={runResearch} disabled={researching}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-all">
            {researching ? <><Loader2 className="h-4 w-4 animate-spin" /> Recherche…</> : <><Globe className="h-4 w-4" /> Lancer la recherche</>}
          </button>
        </div>
        {research && (
          <div className="mt-4 rounded-lg border border-border bg-muted/40 p-4 text-sm text-foreground/90 whitespace-pre-wrap leading-relaxed">
            {research}
          </div>
        )}
      </div>

      {/* Liste des documents */}
      <div className="mt-8">
        <h2 className="mb-3 text-sm font-semibold">Vos documents ({docs.length})</h2>
        {loading ? (
          <div className="flex justify-center py-10"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
        ) : docs.length === 0 ? (
          <div className="card-professional p-8 text-center text-sm text-muted-foreground">
            Aucun document pour l&apos;instant. Ajoutez-en pour que vos agents connaissent votre entreprise en détail.
          </div>
        ) : (
          <div className="space-y-2">
            {docs.map((d) => (
              <div key={d.source} className="card-professional flex items-center justify-between gap-3 p-3.5">
                <div className="flex items-center gap-3 min-w-0">
                  <FileText className="h-4 w-4 shrink-0 text-primary" />
                  <span className="truncate text-sm font-medium">{d.source}</span>
                  <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">{d.chunks} extraits</span>
                </div>
                <button onClick={() => remove(d.source)} className="shrink-0 text-muted-foreground hover:text-destructive" aria-label="Supprimer">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
