import { NextRequest, NextResponse } from 'next/server'
import Anthropic from '@anthropic-ai/sdk'
import { createClient } from '@supabase/supabase-js'
import { buildQuestionsSystemPrompt, buildQuestionsUserPrompt, parseQuestions, type MayaBrief } from '@/lib/video/maya'

/**
 * POST /api/video/questions
 * Maya renvoie 3-5 questions de cadrage à partir d'une idée (avant génération).
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
  try {
    const auth = await verifyAuth(req)
    if (!auth.ok) return NextResponse.json({ error: auth.error }, { status: auth.status })

    const body = await req.json()
    const idea = (body?.idea || '').toString().trim()
    if (!idea) return NextResponse.json({ error: 'Décrivez votre idée de vidéo.' }, { status: 400 })

    const apiKey = process.env.ANTHROPIC_API_KEY
    if (!apiKey) return NextResponse.json({ error: 'Le studio Maya est en cours de configuration (clé API).' }, { status: 503 })

    const brief: MayaBrief = {
      idea: idea.slice(0, 1000),
      platform: body?.platform, objective: body?.objective, duration: body?.duration,
      style: body?.style, audience: body?.audience, language: body?.language,
      voice: body?.voice, avatar: typeof body?.avatar === 'boolean' ? body.avatar : undefined,
    }

    const client = new Anthropic({ apiKey, timeout: 30000 })
    const completion = await client.messages.create({
      model: 'claude-haiku-4-5',
      max_tokens: 500,
      system: buildQuestionsSystemPrompt(),
      messages: [{ role: 'user', content: buildQuestionsUserPrompt(brief) }],
    })
    const text = completion.content.filter((b: any) => b.type === 'text').map((b: any) => b.text).join('\n')

    let questions: string[]
    try { questions = parseQuestions(text) } catch { questions = [] }
    return NextResponse.json({ success: true, questions })
  } catch (error) {
    console.error('Maya questions error:', String(error))
    return NextResponse.json({ error: 'Service momentanément indisponible.' }, { status: 500 })
  }
}
