'use client'

// Panneau « Images » du Studio (Maya) : GÉNÉRER une image (texte → image) et MODIFIER une
// image existante (image + consigne), via OpenAI gpt-image-1. Aperçu + téléchargement.

import { useRef, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { ImagePlus, Wand2, Loader2, Download, Upload } from 'lucide-react'

const SIZES = [
  { id: '1024x1024', label: 'Carré (1:1)' },
  { id: '1024x1536', label: 'Portrait (2:3)' },
  { id: '1536x1024', label: 'Paysage (3:2)' },
]

export function ImageStudioPanel() {
  const [tab, setTab] = useState<'generate' | 'edit'>('generate')
  const [prompt, setPrompt] = useState('')
  const [size, setSize] = useState('1024x1024')
  const [editPrompt, setEditPrompt] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [image, setImage] = useState('') // data URL du résultat
  const fileInput = useRef<HTMLInputElement>(null)
  const [fileName, setFileName] = useState('')

  const token = async () => (await supabase.auth.getSession()).data.session?.access_token || ''

  const generate = async () => {
    if (!prompt.trim() || busy) return
    setBusy(true); setErr(''); setImage('')
    try {
      const res = await fetch('/api/image/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
        body: JSON.stringify({ prompt: prompt.trim(), size }),
      })
      const data = await res.json()
      if (res.ok && data.image) setImage(data.image)
      else setErr(data.error || 'Erreur inattendue.')
    } catch { setErr('Erreur de connexion. Réessayez.') }
    setBusy(false)
  }

  const edit = async () => {
    const file = fileInput.current?.files?.[0]
    if (!file || !editPrompt.trim() || busy) { if (!file) setErr('Choisissez une image à modifier.'); return }
    setBusy(true); setErr(''); setImage('')
    try {
      const fd = new FormData()
      fd.append('image', file)
      fd.append('prompt', editPrompt.trim())
      fd.append('size', size)
      const res = await fetch('/api/image/edit', {
        method: 'POST',
        headers: { Authorization: `Bearer ${await token()}` },
        body: fd,
      })
      const data = await res.json()
      if (res.ok && data.image) setImage(data.image)
      else setErr(data.error || 'Erreur inattendue.')
    } catch { setErr('Erreur de connexion. Réessayez.') }
    setBusy(false)
  }

  return (
    <div className="card-elevated p-6">
      <div className="mb-4 flex items-center gap-2">
        <ImagePlus className="h-5 w-5 text-primary" />
        <h2 className="font-semibold">Images — générer & retoucher</h2>
      </div>

      {/* Onglets */}
      <div className="mb-4 inline-flex rounded-lg border border-border p-0.5 text-sm">
        <button onClick={() => { setTab('generate'); setImage(''); setErr('') }}
          className={`rounded-md px-3 py-1.5 transition-colors ${tab === 'generate' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}>
          Générer
        </button>
        <button onClick={() => { setTab('edit'); setImage(''); setErr('') }}
          className={`rounded-md px-3 py-1.5 transition-colors ${tab === 'edit' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}>
          Modifier
        </button>
      </div>

      {tab === 'generate' ? (
        <>
          <label className="mb-1.5 block text-sm font-medium">Décrivez l’image</label>
          <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3}
            placeholder="Ex : photo produit d’un savon artisanal sur fond beige, lumière douce, style premium."
            className="w-full resize-none rounded-xl border border-border bg-background px-4 py-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary" />
        </>
      ) : (
        <>
          <label className="mb-1.5 block text-sm font-medium">Image à modifier</label>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <input ref={fileInput} type="file" accept="image/*" onChange={(e) => setFileName(e.target.files?.[0]?.name || '')} className="hidden" />
            <button onClick={() => fileInput.current?.click()}
              className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2.5 text-sm font-medium hover:bg-muted transition-colors">
              <Upload className="h-4 w-4" /> Choisir une image
            </button>
            {fileName && <span className="text-xs text-muted-foreground">{fileName}</span>}
          </div>
          <label className="mb-1.5 block text-sm font-medium">Modification souhaitée</label>
          <textarea value={editPrompt} onChange={(e) => setEditPrompt(e.target.value)} rows={2}
            placeholder="Ex : enlève le fond et mets un fond blanc ; ajoute une ombre portée réaliste."
            className="w-full resize-none rounded-xl border border-border bg-background px-4 py-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary" />
        </>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <select value={size} onChange={(e) => setSize(e.target.value)}
          className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none">
          {SIZES.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
        </select>
        <button onClick={tab === 'generate' ? generate : edit} disabled={busy}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors">
          {busy ? <><Loader2 className="h-4 w-4 animate-spin" /> Génération…</> : <><Wand2 className="h-4 w-4" /> {tab === 'generate' ? 'Générer l’image' : 'Appliquer la modification'}</>}
        </button>
      </div>

      {err && <p className="mt-3 text-sm text-destructive break-words">{err}</p>}

      {image && (
        <div className="mt-5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={image} alt="Résultat" className="max-h-[420px] w-auto rounded-xl border border-border" />
          <a href={image} download="image-bapica.png"
            className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors">
            <Download className="h-4 w-4" /> Télécharger
          </a>
        </div>
      )}
    </div>
  )
}
