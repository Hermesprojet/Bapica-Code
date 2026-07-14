import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { pollStatus } from '@/lib/video/engines'

/**
 * POST /api/video/status  { provider, taskId }
 * Interroge le moteur pour l'état d'un rendu → { status: processing|succeeded|failed, url? }
 */

async function verifyAuth(req: NextRequest): Promise<{ ok: true } | { ok: false; status: 401 | 500; error: string }> {
  const token = (req.headers.get('authorization') || '').replace(/^Bearer\s+/i, '').trim()
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
  const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''
  if (!url || !anon) return { ok: false, status: 500, error: 'Configuration Supabase manquante' }
  if (!token) return { ok: false, status: 401, error: 'Non authentifié.' }
  const supabase = createClient(url, anon, { auth: { persistSession: false, autoRefreshToken: false } })
  const { data: { user }, error } = await supabase.auth.getUser(token)
  if (error || !user) return { ok: false, status: 401, error: 'Non authentifié.' }
  return { ok: true }
}

export async function POST(req: NextRequest) {
  const auth = await verifyAuth(req)
  if (!auth.ok) return NextResponse.json({ error: auth.error }, { status: auth.status })

  let body: any
  try { body = await req.json() } catch { return NextResponse.json({ error: 'Corps invalide' }, { status: 400 }) }
  const provider = (body?.provider || '').toString()
  const taskId = (body?.taskId || '').toString()
  if (!provider || !taskId) return NextResponse.json({ error: 'provider et taskId requis' }, { status: 400 })

  try {
    const status = await pollStatus(provider, taskId)
    return NextResponse.json({ success: true, status: status.status, url: status.url })
  } catch (e) {
    return NextResponse.json({ error: String(e instanceof Error ? e.message : e) }, { status: 502 })
  }
}
