// Intégration LinkedIn native (OAuth 2.0 + publication).
// ÉCRIT « à l'aveugle » (non testable en sandbox : pas de clés + réseau bloqué).
// Prérequis en prod : une app LinkedIn avec les produits « Sign In with LinkedIn
// using OpenID Connect » et « Share on LinkedIn », l'URL de redirection déclarée,
// et LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET dans Vercel.

const AUTH_URL = 'https://www.linkedin.com/oauth/v2/authorization'
const TOKEN_URL = 'https://www.linkedin.com/oauth/v2/accessToken'
const USERINFO_URL = 'https://api.linkedin.com/v2/userinfo'
const UGC_URL = 'https://api.linkedin.com/v2/ugcPosts'

// Scopes : identité (OpenID) + publication au nom du membre.
const SCOPES = 'openid profile email w_member_social'

export function linkedinConfigured(): boolean {
  return !!(process.env.LINKEDIN_CLIENT_ID && process.env.LINKEDIN_CLIENT_SECRET)
}

export function redirectUri(): string {
  const base = (process.env.NEXT_PUBLIC_APP_URL || '').replace(/\/$/, '')
  return process.env.LINKEDIN_REDIRECT_URI || `${base}/api/social/linkedin/callback`
}

export function buildAuthUrl(state: string): string {
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: process.env.LINKEDIN_CLIENT_ID || '',
    redirect_uri: redirectUri(),
    scope: SCOPES,
    state,
  })
  return `${AUTH_URL}?${params.toString()}`
}

// Échange le code d'autorisation contre un access_token.
export async function exchangeCode(code: string): Promise<{ accessToken: string; expiresIn: number }> {
  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    code,
    redirect_uri: redirectUri(),
    client_id: process.env.LINKEDIN_CLIENT_ID || '',
    client_secret: process.env.LINKEDIN_CLIENT_SECRET || '',
  })
  const res = await fetch(TOKEN_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  })
  const data = await res.json()
  if (!res.ok || !data.access_token) throw new Error(`LinkedIn token : ${data.error_description || data.error || JSON.stringify(data)}`)
  return { accessToken: data.access_token, expiresIn: Number(data.expires_in) || 0 }
}

// Récupère l'identifiant membre (sub) → URN "urn:li:person:{sub}".
export async function getMemberSub(accessToken: string): Promise<string> {
  const res = await fetch(USERINFO_URL, { headers: { Authorization: `Bearer ${accessToken}` } })
  const data = await res.json()
  if (!res.ok || !data.sub) throw new Error(`LinkedIn userinfo : ${data.message || JSON.stringify(data)}`)
  return String(data.sub)
}

// Publie un post texte au nom du membre.
export async function publishText(accessToken: string, memberSub: string, text: string): Promise<{ id: string }> {
  const res = await fetch(UGC_URL, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'X-Restli-Protocol-Version': '2.0.0',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      author: `urn:li:person:${memberSub}`,
      lifecycleState: 'PUBLISHED',
      specificContent: {
        'com.linkedin.ugc.ShareContent': {
          shareCommentary: { text: text.slice(0, 2900) },
          shareMediaCategory: 'NONE',
        },
      },
      visibility: { 'com.linkedin.ugc.MemberNetworkVisibility': 'PUBLIC' },
    }),
  })
  if (!res.ok) {
    let msg = ''
    try { msg = JSON.stringify(await res.json()) } catch { msg = await res.text() }
    throw new Error(`LinkedIn publication : ${msg}`)
  }
  const id = res.headers.get('x-restli-id') || res.headers.get('X-RestLi-Id') || ''
  return { id }
}
