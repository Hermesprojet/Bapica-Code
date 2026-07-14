import { NextRequest } from 'next/server'
import { createClient } from '@supabase/supabase-js'

// Extrait le jeton Bearer de la requête.
export function bearerToken(req: NextRequest): string {
  return (req.headers.get('authorization') || '').replace(/^Bearer\s+/i, '').trim()
}

// Valide un jeton Supabase et renvoie l'utilisateur (ou null). Client paresseux.
export async function getUserFromToken(token: string) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
  const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''
  if (!url || !anon || !token) return null
  const supabase = createClient(url, anon, { auth: { persistSession: false, autoRefreshToken: false } })
  const { data: { user }, error } = await supabase.auth.getUser(token)
  return error ? null : user
}
