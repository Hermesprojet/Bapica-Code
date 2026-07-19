'use client'

import { useState } from 'react'
import { Search, Loader2, AlertCircle, Linkedin, Mail, Building2, Users } from 'lucide-react'
import { supabase } from '@/lib/supabase'

interface Lead {
  name: string
  title: string
  company: string
  location: string
  linkedinUrl: string
  email: string | null
  emailLocked: boolean
}

const SIZES = [
  { label: 'Toutes tailles', value: '' },
  { label: '1–10', value: '1,10' },
  { label: '11–50', value: '11,50' },
  { label: '51–200', value: '51,200' },
  { label: '201–1000', value: '201,1000' },
  { label: '1000+', value: '1001,100000' },
]

/**
 * Panneau « Trouver des prospects » (Apollo) pour les agents commerciaux.
 * Alimente POST /api/leads/search. Sans APOLLO_API_KEY, un message le signale.
 */
export function LeadFinderPanel({ persona }: { persona: string }) {
  const [open, setOpen] = useState(false)
  const [titles, setTitles] = useState('')
  const [location, setLocation] = useState('')
  const [keywords, setKeywords] = useState('')
  const [size, setSize] = useState('')
  const [status, setStatus] = useState<'idle' | 'searching' | 'done' | 'err'>('idle')
  const [error, setError] = useState('')
  const [leads, setLeads] = useState<Lead[]>([])
  const [total, setTotal] = useState(0)

  const search = async () => {
    if (status === 'searching') return
    if (!titles.trim() && !keywords.trim() && !location.trim()) {
      setStatus('err'); setError('Renseignez au moins un poste, un mot-clé ou un lieu.'); return
    }
    setStatus('searching'); setError(''); setLeads([])
    try {
      const { data: { session } } = await supabase.auth.getSession()
      const token = session?.access_token || ''
      const res = await fetch('/api/leads/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          titles: titles.trim(),
          locations: location.trim(),
          keywords: keywords.trim(),
          employeeRanges: size ? [size] : undefined,
        }),
      })
      const data = await res.json()
      if (res.ok && data.success) {
        setLeads(data.leads || [])
        setTotal(data.total || 0)
        setStatus('done')
      } else {
        setStatus('err'); setError(data.error || 'Échec de la recherche.')
      }
    } catch {
      setStatus('err'); setError('Erreur de connexion.')
    }
  }

  return (
    <div className="rounded-xl border border-border bg-card">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-sm font-semibold"
      >
        <span className="flex items-center gap-2">
          <Search className="h-4 w-4 text-primary" />
          Trouver des prospects avec {persona}
        </span>
        <span className="text-xs text-muted-foreground">{open ? 'Fermer' : 'Ouvrir'}</span>
      </button>

      {open && (
        <div className="border-t border-border p-4 space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              value={titles}
              onChange={(e) => setTitles(e.target.value)}
              placeholder="Poste(s) : Directeur commercial, DAF…"
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="Lieu : France, Paris, Lyon…"
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <input
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="Secteur / mots-clés : restauration, SaaS…"
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <select
              value={size}
              onChange={(e) => setSize(e.target.value)}
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              {SIZES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>

          <div className="flex items-center justify-between gap-3">
            {status === 'err' ? (
              <span className="inline-flex items-center gap-1.5 text-xs text-destructive">
                <AlertCircle className="h-3.5 w-3.5" /> {error}
              </span>
            ) : status === 'done' ? (
              <span className="text-xs text-muted-foreground">{total.toLocaleString('fr-FR')} prospects trouvés — {leads.length} affichés</span>
            ) : <span />}
            <button
              onClick={search}
              disabled={status === 'searching'}
              className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {status === 'searching' ? <><Loader2 className="h-4 w-4 animate-spin" /> Recherche…</> : <><Search className="h-4 w-4" /> Rechercher</>}
            </button>
          </div>

          {/* Résultats */}
          {leads.length > 0 && (
            <div className="space-y-2 pt-1">
              {leads.map((lead, i) => (
                <div key={i} className="rounded-lg border border-border p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-semibold text-sm">{lead.name}</div>
                      <div className="text-xs text-muted-foreground">{lead.title}</div>
                      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                        {lead.company && <span className="inline-flex items-center gap-1"><Building2 className="h-3 w-3" />{lead.company}</span>}
                        {lead.location && <span className="inline-flex items-center gap-1"><Users className="h-3 w-3" />{lead.location}</span>}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {lead.linkedinUrl && (
                        <a href={lead.linkedinUrl} target="_blank" rel="noopener noreferrer" className="text-[#0A66C2] hover:opacity-80" aria-label="LinkedIn">
                          <Linkedin className="h-4 w-4" />
                        </a>
                      )}
                      {lead.email ? (
                        <a href={`mailto:${lead.email}`} className="inline-flex items-center gap-1 text-xs text-primary hover:underline">
                          <Mail className="h-3.5 w-3.5" /> {lead.email}
                        </a>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground" title="Email non révélé (crédit Apollo requis)">
                          <Mail className="h-3.5 w-3.5" /> email verrouillé
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          <p className="text-[11px] text-muted-foreground">
            Résultats réels via Apollo.io (clé APOLLO_API_KEY requise). Les emails masqués nécessitent
            un crédit d&apos;enrichissement Apollo pour être révélés.
          </p>
        </div>
      )}
    </div>
  )
}
