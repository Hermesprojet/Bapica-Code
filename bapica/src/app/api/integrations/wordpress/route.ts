import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { saveConnection, getConnection, deleteConnection } from '@/lib/social/store'

/**
 * Connexion d'un site WordPress via l'API REST + « mot de passe d'application »
 * (Comptes → Profil → Mots de passe d'application). Pas d'OAuth, pas de plugin.
 * Permet à Camille d'auditer ET de modifier le site (titres, contenus), avec
 * validation via « Actions à valider ».
 */
export async function GET(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  try {
    const conn = await getConnection(user.id, 'wordpress')
    if (!conn) return NextResponse.json({ connected: false })
    let meta: { siteUrl?: string } = {}
    try { meta = JSON.parse((conn as { external_id?: string }).external_id || '{}') } catch { /* ignore */ }
    return NextResponse.json({ connected: true, siteUrl: meta.siteUrl || '' })
  } catch {
    return NextResponse.json({ connected: false })
  }
}

export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  let b: any = {}
  try { b = await req.json() } catch { return NextResponse.json({ error: 'Requête invalide.' }, { status: 400 }) }

  let siteUrl = String(b.siteUrl || '').trim().replace(/\/$/, '')
  const wpUser = String(b.user || '').trim()
  const appPassword = String(b.appPassword || '').replace(/\s+/g, '') // WP affiche le mdp avec des espaces

  if (!/^https?:\/\//i.test(siteUrl)) siteUrl = `https://${siteUrl}`
  try { new URL(siteUrl) } catch { return NextResponse.json({ error: 'URL du site invalide.' }, { status: 400 }) }
  if (!wpUser || !appPassword) {
    return NextResponse.json({ error: "Nom d'utilisateur et mot de passe d'application requis." }, { status: 400 })
  }

  // Vérifie les identifiants via /users/me (contexte edit = nécessite l'auth).
  const basic = Buffer.from(`${wpUser}:${appPassword}`).toString('base64')
  try {
    const res = await fetch(`${siteUrl}/wp-json/wp/v2/users/me?context=edit`, {
      headers: { Authorization: `Basic ${basic}`, Accept: 'application/json' },
      signal: AbortSignal.timeout(12000),
    })
    if (!res.ok) {
      const txt = await res.text().catch(() => '')
      return NextResponse.json(
        { error: `WordPress a refusé la connexion (HTTP ${res.status}). Vérifiez l'URL, l'utilisateur et le mot de passe d'application. ${txt.slice(0, 200)}` },
        { status: 400 }
      )
    }
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e)
    return NextResponse.json({ error: `Site injoignable ou API REST désactivée — ${msg}` }, { status: 400 })
  }

  try {
    await saveConnection(user.id, 'wordpress', {
      accessToken: appPassword,
      externalId: JSON.stringify({ siteUrl, user: wpUser }),
    })
    return NextResponse.json({ success: true, siteUrl })
  } catch (e) {
    const msg = String(e instanceof Error ? e.message : e)
    if (/does not exist|42P01/i.test(msg)) {
      return NextResponse.json({ error: 'Base non initialisée : exécutez supabase-schema.sql.' }, { status: 400 })
    }
    return NextResponse.json({ error: `Enregistrement impossible : ${msg}` }, { status: 500 })
  }
}

export async function DELETE(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  try {
    await deleteConnection(user.id, 'wordpress')
    return NextResponse.json({ success: true })
  } catch (e) {
    return NextResponse.json({ error: String(e instanceof Error ? e.message : e) }, { status: 500 })
  }
}
