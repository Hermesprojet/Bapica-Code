import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { getCurrentUsage, isWithinQuota, logUsage, getQuotaMessage } from '@/lib/usage-limits'

interface VideoJob {
  id: string
  user_id: string
  provider: 'heygen' | 'runway' | 'elevenlabs'
  type: 'avatar' | 'generative' | 'voiceover'
  script: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  video_url?: string
  error?: string
  created_at: string
}

// POST /api/video/generate — Lance un job vidéo non-bloquant
export async function POST(req: NextRequest) {
  try {
    const supabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL || '',
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '',
      { auth: { persistSession: false, autoRefreshToken: false } }
    )
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) {
      return NextResponse.json({ error: 'Non authentifié' }, { status: 401 })
    }

    // Vérifier le quota utilisateur
    const currentUsage = await getCurrentUsage(user.id)
    const plan = user.user_metadata?.plan || 'essential'
    
    const quotaMsg = getQuotaMessage(currentUsage, plan, 'videos')
    if (quotaMsg) {
      return NextResponse.json({ success: false, error: quotaMsg }, { status: 429 })
    }

    const { script, provider = 'heygen', type = 'avatar', voiceId, avatarId } = await req.json()

    if (!script?.trim()) {
      return NextResponse.json({ success: false, error: 'Script requis.' }, { status: 400 })
    }

    // Créer le job
    const jobId = crypto.randomUUID()
    const job: VideoJob = {
      id: jobId,
      user_id: user.id,
      provider,
      type,
      script: script.slice(0, 5000),
      status: 'pending',
      created_at: new Date().toISOString(),
    }

    await supabase.from('video_jobs').insert(job)

    // Lancer la génération en arrière-plan (non-bloquant)
    logUsage(user.id, 'videos').catch(() => {})
    generateVideo(job, voiceId, avatarId).catch(err => {
      console.error('Video generation failed:', err)
      supabase.from('video_jobs').update({ status: 'failed', error: String(err) }).eq('id', jobId)
    })

    return NextResponse.json({ success: true, jobId, status: 'pending' })
  } catch (error) {
    console.error('Video route error:', error)
    return NextResponse.json({ success: false, error: 'Erreur interne' }, { status: 500 })
  }
}

// GET /api/video/generate?jobId=xxx — Poll le statut
export async function GET(req: NextRequest) {
  const jobId = req.nextUrl.searchParams.get('jobId')
  if (!jobId) {
    return NextResponse.json({ error: 'jobId requis' }, { status: 400 })
  }

  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL || '',
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''
  )

  const { data } = await supabase.from('video_jobs').select('*').eq('id', jobId).single()
  if (!data) {
    return NextResponse.json({ error: 'Job introuvable' }, { status: 404 })
  }

  return NextResponse.json({ 
    status: data.status, 
    videoUrl: data.video_url, 
    error: data.error 
  })
}

// Génération asynchrone (appelée en arrière-plan, pas dans la réponse HTTP)
async function generateVideo(job: VideoJob, voiceId?: string, avatarId?: string) {
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL || '',
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''
  )

  await supabase.from('video_jobs').update({ status: 'processing' }).eq('id', job.id)

  try {
    let result: string | null = null

    switch (job.provider) {
      case 'heygen': {
        const apiKey = process.env.HEYGEN_API_KEY
        if (!apiKey) throw new Error('HEYGEN_API_KEY non configurée')

        const res = await fetch('https://api.heygen.com/v2/video/generate', {
          method: 'POST',
          headers: { 'X-Api-Key': apiKey, 'Content-Type': 'application/json' },
          body: JSON.stringify({
            video_inputs: [{
              character: { type: 'avatar', avatar_id: avatarId || process.env.HEYGEN_AVATAR_ID, avatar_style: 'normal' },
              voice: { type: 'text', input_text: job.script, voice_id: voiceId || process.env.HEYGEN_VOICE_ID },
            }],
            dimension: { width: 1920, height: 1080 },
          }),
        })

        const data = await res.json()
        if (!res.ok) throw new Error(data?.error?.message || 'Erreur HeyGen')
        
        const videoId = data?.data?.video_id
        if (!videoId) throw new Error('Pas de video_id retourné')

        // Polling (max 2 min) — pour la prod, utiliser un webhook HeyGen
        for (let i = 0; i < 24; i++) {
          await new Promise(r => setTimeout(r, 5000))
          const statusRes = await fetch(`https://api.heygen.com/v1/video_status.get?video_id=${videoId}`, {
            headers: { 'X-Api-Key': apiKey },
          })
          const statusData = await statusRes.json()
          if (statusData?.data?.status === 'completed') {
            result = statusData.data.video_url
            break
          }
          if (statusData?.data?.status === 'failed') {
            throw new Error(statusData.data.error || 'Échec HeyGen')
          }
        }
        if (!result) throw new Error('Timeout — la vidéo prend plus de 2 min')
        break
      }

      case 'elevenlabs': {
        const apiKey = process.env.ELEVENLABS_API_KEY
        if (!apiKey) throw new Error('ELEVENLABS_API_KEY non configurée')

        const res = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${voiceId || '21m00Tcm4TlvDq8ikWAM'}`, {
          method: 'POST',
          headers: { 'xi-api-key': apiKey, 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: job.script, model_id: 'eleven_multilingual_v2' }),
        })

        if (!res.ok) throw new Error('Erreur ElevenLabs')
        const buffer = await res.arrayBuffer()
        // Stocker dans Supabase Storage
        const fileName = `voiceovers/${job.id}.mp3`
        const { error: uploadError } = await supabase.storage.from('media').upload(fileName, buffer, { contentType: 'audio/mpeg', upsert: true })
        if (uploadError) throw new Error('Erreur upload')
        
        const { data: urlData } = supabase.storage.from('media').getPublicUrl(fileName)
        result = urlData.publicUrl
        break
      }

      case 'runway': {
        const apiKey = process.env.RUNWAY_API_KEY
        if (!apiKey) throw new Error('RUNWAY_API_KEY non configurée')

        const res = await fetch('https://api.runwayml.com/v1/generate', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt: job.script, model: 'gen3', num_results: 1 }),
        })

        const data = await res.json()
        result = data?.output?.[0] || null
        if (!result) throw new Error('Erreur Runway')
        break
      }
    }

    await supabase.from('video_jobs').update({ status: 'completed', video_url: result }).eq('id', job.id)
  } catch (error) {
    await supabase.from('video_jobs').update({ status: 'failed', error: String(error) }).eq('id', job.id)
  }
}
