import { NextRequest, NextResponse } from 'next/server'
import { exec } from 'child_process'
import { promisify } from 'util'
import { writeFile, mkdir, readFile } from 'fs/promises'
import { createClient } from '@supabase/supabase-js'
import path from 'path'
import os from 'os'

const execAsync = promisify(exec)

/**
 * POST /api/video/assemble
 * Assemble des clips + voix-off + musique en une vidéo montée.
 * 
 * Body: {
 *   clips: string[]       // URLs des clips (Runway/HeyGen)
 *   voiceover: string     // URL de la voix-off (ElevenLabs)
 *   music?: string        // URL musique de fond (optionnel)
 *   format?: 'vertical' | 'horizontal'  // défaut: 'horizontal'
 * }
 * 
 * ⚠️ Nécessite FFmpeg installé sur le serveur.
 * Sur Vercel serverless, FFmpeg n'est PAS disponible.
 * Utiliser Railway, Fly.io, ou un container Docker.
 */

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

    const { clips, voiceover, music, format = 'horizontal' } = await req.json()

    if (!clips?.length || !voiceover) {
      return NextResponse.json({ error: 'clips et voiceover requis' }, { status: 400 })
    }

    // Vérifier que FFmpeg est disponible
    try {
      await execAsync('ffmpeg -version')
    } catch {
      return NextResponse.json({ 
        error: 'FFmpeg non disponible sur cette instance. Utiliser Railway ou Fly.io.',
        hint: 'Déployez cette route sur un service avec FFmpeg (Railway, Fly.io, Docker)'
      }, { status: 501 })
    }

    const workDir = path.join(os.tmpdir(), `bapica-assemble-${Date.now()}`)
    await mkdir(workDir, { recursive: true })

    // 1. Télécharger tous les fichiers
    const clipFiles: string[] = []
    for (let i = 0; i < clips.length; i++) {
      const clipPath = path.join(workDir, `clip_${i}.mp4`)
      await downloadFile(clips[i], clipPath)
      clipFiles.push(clipPath)
    }

    const voicePath = path.join(workDir, 'voiceover.mp3')
    await downloadFile(voiceover, voicePath)

    // 2. Créer la liste de concaténation
    const concatList = clipFiles.map(f => `file '${f}'`).join('\n')
    const concatFile = path.join(workDir, 'concat.txt')
    await writeFile(concatFile, concatList)

    // 3. Assembler avec FFmpeg
    const outputFile = path.join(workDir, 'output.mp4')
    const dimension = format === 'vertical' ? '1080:1920' : '1920:1080'

    let ffmpegCmd = `ffmpeg -y -f concat -safe 0 -i "${concatFile}" -i "${voicePath}"`

    if (music) {
      const musicPath = path.join(workDir, 'music.mp3')
      await downloadFile(music, musicPath)
      ffmpegCmd += ` -i "${musicPath}"`
      // Voix 100%, musique 15%
      ffmpegCmd += ` -filter_complex "[1:a]volume=1.0[voice];[2:a]volume=0.15[bgm];[voice][bgm]amix=inputs=2:duration=first[audio]" -map 0:v -map "[audio]"`
    } else {
      ffmpegCmd += ` -map 0:v -map 1:a`
    }

    ffmpegCmd += ` -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p -vf "scale=${dimension}:force_original_aspect_ratio=decrease,pad=${dimension}:(ow-iw)/2:(oh-ih)/2" -c:a aac -b:a 128k -shortest -movflags +faststart "${outputFile}"`

    await execAsync(ffmpegCmd, { timeout: 120000 })

    // 4. Upload vers Supabase Storage
    const videoBuffer = await readFile(outputFile)
    const fileName = `assembled/${user.id}/${Date.now()}.mp4`
    
    const { error: uploadError } = await supabase.storage
      .from('media')
      .upload(fileName, videoBuffer, { contentType: 'video/mp4', upsert: true })
    
    if (uploadError) throw new Error('Upload failed')

    const { data: urlData } = supabase.storage.from('media').getPublicUrl(fileName)

    // Nettoyer
    await execAsync(`rm -rf "${workDir}"`).catch(() => {})

    return NextResponse.json({ success: true, videoUrl: urlData.publicUrl })
  } catch (error) {
    console.error('Assembly error:', error)
    return NextResponse.json({ success: false, error: String(error) }, { status: 500 })
  }
}

async function downloadFile(url: string, dest: string) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Download failed: ${url}`)
  const buffer = Buffer.from(await res.arrayBuffer())
  await writeFile(dest, buffer)
}
