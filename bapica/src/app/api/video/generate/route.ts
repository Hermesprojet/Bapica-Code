import { NextResponse } from 'next/server'

// Dimensions par format (id envoyé par le formulaire vidéo).
const DIMENSIONS: Record<string, { width: number; height: number }> = {
  landscape: { width: 1920, height: 1080 },
  portrait: { width: 1080, height: 1920 },
  square: { width: 1080, height: 1080 },
}

// POST /api/video/generate
// Body: { script, language, aspect_ratio, title }
// Génère une vidéo avec avatar IA via l'API HeyGen v2.
export async function POST(req: Request) {
  try {
    const body = await req.json()
    const { script, aspect_ratio } = body

    const apiKey = process.env.HEYGEN_API_KEY
    const avatarId = process.env.HEYGEN_AVATAR_ID
    const voiceId = process.env.HEYGEN_VOICE_ID

    if (!apiKey) {
      return NextResponse.json(
        { success: false, error: 'Clé API HeyGen (HEYGEN_API_KEY) non configurée.' },
        { status: 400 }
      )
    }
    if (!avatarId || !voiceId) {
      return NextResponse.json(
        {
          success: false,
          error:
            'Avatar/voix HeyGen non configurés (HEYGEN_AVATAR_ID, HEYGEN_VOICE_ID).',
        },
        { status: 400 }
      )
    }
    if (!script || typeof script !== 'string' || !script.trim()) {
      return NextResponse.json(
        { success: false, error: 'Script requis.' },
        { status: 400 }
      )
    }

    const dimension = DIMENSIONS[aspect_ratio as string] || DIMENSIONS.landscape

    const response = await fetch('https://api.heygen.com/v2/video/generate', {
      method: 'POST',
      headers: {
        'X-Api-Key': apiKey,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        video_inputs: [
          {
            character: {
              type: 'avatar',
              avatar_id: avatarId,
              avatar_style: 'normal',
            },
            voice: {
              type: 'text',
              input_text: script,
              voice_id: voiceId,
            },
          },
        ],
        dimension,
      }),
    })

    const data = await response.json()

    if (!response.ok || data.error) {
      console.error('HeyGen API error:', data)
      return NextResponse.json(
        {
          success: false,
          error:
            data?.error?.message ||
            data?.message ||
            'Erreur lors de la génération de la vidéo.',
        },
        { status: 502 }
      )
    }

    // L'identifiant de vidéo permet d'interroger le statut côté HeyGen.
    return NextResponse.json({
      success: true,
      videoId: data?.data?.video_id ?? null,
    })
  } catch (error) {
    console.error('Video generation error:', error)
    return NextResponse.json(
      { success: false, error: 'Erreur interne du serveur' },
      { status: 500 }
    )
  }
}
