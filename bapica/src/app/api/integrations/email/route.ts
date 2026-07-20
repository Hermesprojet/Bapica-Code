import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { saveConnection, getConnection, deleteConnection } from '@/lib/social/store'
import { verifyEmail, type EmailConfig } from '@/lib/email'

/**
 * Connexion d'une boîte email par IMAP/SMTP (n'importe quel fournisseur).
 * POST { email, password, imapHost, imapPort, smtpHost, smtpPort, user? } → vérifie puis stocke.
 * GET → état de la connexion email. DELETE → déconnecte.
 * Le mot de passe est stocké dans access_token ; la config (hors mdp) dans external_id.
 */
export async function GET(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  try {
    const conn = await getConnection(user.id, 'email')
    if (!conn) return NextResponse.json({ connected: false })
    let meta: { email?: string } = {}
    try { meta = JSON.parse((conn as { external_id?: string }).external_id || '{}') } catch { /* ignore */ }
    return NextResponse.json({ connected: true, email: meta.email || '' })
  } catch {
    return NextResponse.json({ connected: false })
  }
}

export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })

  let b: any = {}
  try { b = await req.json() } catch { return NextResponse.json({ error: 'Requête invalide.' }, { status: 400 }) }

  const cfg: EmailConfig = {
    email: String(b.email || '').trim(),
    user: String(b.user || b.email || '').trim(),
    password: String(b.password || ''),
    imapHost: String(b.imapHost || '').trim(),
    imapPort: Number(b.imapPort) || 993,
    smtpHost: String(b.smtpHost || '').trim(),
    smtpPort: Number(b.smtpPort) || 465,
  }

  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(cfg.email)) {
    return NextResponse.json({ error: 'Adresse email invalide.' }, { status: 400 })
  }
  if (!cfg.password || !cfg.imapHost || !cfg.smtpHost) {
    return NextResponse.json({ error: 'Mot de passe, serveur IMAP et serveur SMTP requis.' }, { status: 400 })
  }

  const check = await verifyEmail(cfg)
  if (!check.ok) {
    return NextResponse.json({ error: `Connexion refusée — ${check.error}` }, { status: 400 })
  }

  try {
    await saveConnection(user.id, 'email', {
      accessToken: cfg.password,
      externalId: JSON.stringify({
        email: cfg.email, user: cfg.user,
        imapHost: cfg.imapHost, imapPort: cfg.imapPort,
        smtpHost: cfg.smtpHost, smtpPort: cfg.smtpPort,
      }),
    })
    return NextResponse.json({ success: true, email: cfg.email })
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
    await deleteConnection(user.id, 'email')
    return NextResponse.json({ success: true })
  } catch (e) {
    return NextResponse.json({ error: String(e instanceof Error ? e.message : e) }, { status: 500 })
  }
}
