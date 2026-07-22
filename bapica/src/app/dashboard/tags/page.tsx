'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { Tag, Trash2, Loader2, AlertCircle } from 'lucide-react'

interface TagRow {
  id: string
  agent_id: string | null
  channel: string | null
  contact: string | null
  tag: string
  note: string | null
  created_at: string
}

const TAG_LABELS: Record<string, string> = {
  prospect_interesse: 'Prospect intéressé',
  rappel_demande: 'Rappel demandé',
  sav: 'SAV',
  impaye: 'Impayé',
  pas_interesse: 'Pas intéressé',
  autre: 'Autre',
}

const TAG_COLOR: Record<string, string> = {
  prospect_interesse: 'bg-emerald-500/10 text-emerald-700',
  rappel_demande: 'bg-amber-500/10 text-amber-700',
  sav: 'bg-blue-500/10 text-blue-700',
  impaye: 'bg-rose-500/10 text-rose-700',
  pas_interesse: 'bg-slate-500/10 text-slate-600',
  autre: 'bg-muted text-muted-foreground',
}

export default function TagsPage() {
  const [rows, setRows] = useState<TagRow[]>([])
  const [loading, setLoading] = useState(true)
  const [needsSetup, setNeedsSetup] = useState(false)
  const [filter, setFilter] = useState<string>('')
  const [busy, setBusy] = useState<string | null>(null)

  const token = async () => (await supabase.auth.getSession()).data.session?.access_token || ''

  const load = async (tag = filter) => {
    setLoading(true)
    try {
      const q = tag ? `?tag=${encodeURIComponent(tag)}` : ''
      const res = await fetch(`/api/tags${q}`, { headers: { Authorization: `Bearer ${await token()}` } })
      const data = await res.json()
      if (res.ok) { setRows(data.tags || []); setNeedsSetup(Boolean(data.needsSetup)) }
    } catch { /* ignore */ }
    setLoading(false)
  }

  useEffect(() => { load('') }, [])

  const applyFilter = (tag: string) => { setFilter(tag); load(tag) }

  const remove = async (id: string) => {
    setBusy(id)
    try {
      await fetch('/api/tags', {
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
        <h1 className="text-2xl font-bold">Étiquettes</h1>
        <p className="mt-1 text-muted-foreground">
          Chaque échange qualifié par vos agents (prospect intéressé, rappel, SAV, impayé…) est tagué ici,
          triable en un coup d&apos;œil.
        </p>
      </div>

      {/* Filtres */}
      <div className="mb-6 flex flex-wrap gap-2">
        <button
          onClick={() => applyFilter('')}
          className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${filter === '' ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:text-foreground'}`}
        >
          Toutes
        </button>
        {Object.entries(TAG_LABELS).map(([value, label]) => (
          <button
            key={value}
            onClick={() => applyFilter(value)}
            className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${filter === value ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:text-foreground'}`}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
      ) : needsSetup ? (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-5 text-sm">
          <div className="flex items-center gap-2 font-semibold text-amber-700"><AlertCircle className="h-4 w-4" /> Base non initialisée</div>
          <p className="mt-2 text-muted-foreground">
            La table <code className="rounded bg-muted px-1">interaction_tags</code> est absente : exécutez
            <code className="rounded bg-muted px-1">bapica/supabase-schema.sql</code> dans Supabase → SQL Editor.
          </p>
        </div>
      ) : rows.length === 0 ? (
        <div className="card-professional flex items-center gap-3 p-6 text-sm text-muted-foreground">
          <Tag className="h-5 w-5 text-primary" />
          Aucune étiquette{filter ? ' pour ce filtre' : ''}. Vos agents en créent au fil des échanges.
        </div>
      ) : (
        <div className="space-y-2">
          {rows.map((r) => (
            <div key={r.id} className="card-professional flex items-center justify-between gap-3 p-4">
              <div className="flex min-w-0 items-center gap-3">
                <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${TAG_COLOR[r.tag] || TAG_COLOR.autre}`}>
                  {TAG_LABELS[r.tag] || r.tag}
                </span>
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{r.contact || 'Contact non précisé'}</div>
                  <div className="truncate text-[11px] text-muted-foreground">
                    {[r.channel, r.agent_id, new Date(r.created_at).toLocaleDateString('fr')].filter(Boolean).join(' · ')}
                    {r.note ? ` — ${r.note}` : ''}
                  </div>
                </div>
              </div>
              <button onClick={() => remove(r.id)} disabled={busy === r.id} className="shrink-0 text-muted-foreground hover:text-destructive transition-colors" aria-label="Supprimer">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
