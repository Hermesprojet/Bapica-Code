import { NextRequest, NextResponse } from 'next/server'
import { bearerToken, getUserFromToken } from '@/lib/api-auth'
import { connectBank, listInstitutions, createLink, refreshAccounts, bankStatus, BANK_PLATFORM } from '@/lib/bank/gocardless'
import { deleteConnection } from '@/lib/social/store'

/**
 * Connecteur bancaire GoCardless Bank Account Data (lecture seule).
 * GET  /api/bank                              → état (connecté ? banque liée ? nb comptes)
 * POST /api/bank { action, ... }              → 'connect' | 'institutions' | 'link' | 'accounts'
 * DELETE /api/bank                            → déconnexion
 */
export async function GET(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  return NextResponse.json(await bankStatus(user.id))
}

export async function POST(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  let body: any = {}
  try { body = await req.json() } catch { return NextResponse.json({ error: 'Requête invalide.' }, { status: 400 }) }
  const action = String(body.action || '')

  if (action === 'connect') {
    const r = await connectBank(user.id, String(body.secretId || '').trim(), String(body.secretKey || '').trim())
    return r.ok ? NextResponse.json({ success: true }) : NextResponse.json({ error: r.error }, { status: 400 })
  }
  if (action === 'institutions') {
    const r = await listInstitutions(user.id, String(body.country || 'FR'))
    return r.ok ? NextResponse.json({ institutions: r.institutions }) : NextResponse.json({ error: r.error }, { status: 400 })
  }
  if (action === 'link') {
    const redirect = `${req.nextUrl.origin}/dashboard/connections?connected=banque`
    const r = await createLink(user.id, String(body.institutionId || ''), redirect)
    return r.ok ? NextResponse.json({ link: r.link }) : NextResponse.json({ error: r.error }, { status: 400 })
  }
  if (action === 'accounts') {
    const r = await refreshAccounts(user.id)
    return r.ok ? NextResponse.json({ accounts: r.accounts }) : NextResponse.json({ error: r.error }, { status: 400 })
  }
  return NextResponse.json({ error: 'Action inconnue.' }, { status: 400 })
}

export async function DELETE(req: NextRequest) {
  const user = await getUserFromToken(bearerToken(req))
  if (!user) return NextResponse.json({ error: 'Non autorisé' }, { status: 401 })
  await deleteConnection(user.id, BANK_PLATFORM)
  return NextResponse.json({ success: true })
}
