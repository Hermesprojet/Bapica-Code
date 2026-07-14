import { NextRequest, NextResponse } from 'next/server'
import Anthropic from '@anthropic-ai/sdk'
import { createClient } from '@supabase/supabase-js'
import {
  buildMayaSystemPrompt,
  buildMayaUserPrompt,
  parseProductionPackage,
  type MayaBrief,
} from '@/lib/video/maya'

/**
 * POST /api/video/orchestrate
 * Le « cerveau » de Maya : idée -> package de production complet (JSON).
 * Ne rend AUCUN MP4 ; produit le script, le storyboard et les prompts prêts
 * pour les moteurs (Runway / Veo / HeyGen / Kling…).
 */

// Auth par jeton Bearer Supabase (instanciation paresseuse — jamais au niveau module).
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
  try {
    const auth = await verifyAuth(req)
    if (!auth.ok) return NextResponse.json({ error: auth.error }, { status: auth.status })

    const body = await req.json()
    const idea = (body?.idea || '').toString().trim()
    if (!idea) {
      return NextResponse.json({ error: 'Décrivez votre idée de vidéo.' }, { status: 400 })
    }

    const apiKey = process.env.ANTHROPIC_API_KEY
    if (!apiKey) {
      return NextResponse.json(
        { error: 'Le studio Maya est en cours de configuration (clé API).' },
        { status: 503 }
      )
    }

    const brief: MayaBrief = {
      idea: idea.slice(0, 1000),
      platform: body?.platform,
      objective: body?.objective,
      duration: body?.duration,
      style: body?.style,
      audience: body?.audience,
      language: body?.language,
      voice: body?.voice,
      avatar: typeof body?.avatar === 'boolean' ? body.avatar : undefined,
      clarifications: body?.clarifications ? String(body.clarifications).slice(0, 2000) : undefined,
    }

    const client = new Anthropic({ apiKey, timeout: 60000 })
    const completion = await client.messages.create({
      model: 'claude-sonnet-4-5',
      max_tokens: 4000,
      system: buildMayaSystemPrompt(),
      messages: [{ role: 'user', content: buildMayaUserPrompt(brief) }],
    })

    const text = completion.content
      .filter((b: any) => b.type === 'text')
      .map((b: any) => b.text)
      .join('\n')

    let pkg
    try {
      pkg = parseProductionPackage(text)
    } catch (e) {
      return NextResponse.json(
        { error: 'Maya a produit une réponse inattendue. Réessayez en reformulant votre idée.' },
        { status: 422 }
      )
    }

    return NextResponse.json({ success: true, package: pkg })
  } catch (error) {
    console.error('Maya orchestrate error:', String(error))
    return NextResponse.json({ error: 'Service momentanément indisponible.' }, { status: 500 })
  }
}
