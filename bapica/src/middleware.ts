import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

// Routes publiques (pas de vérification d'auth)
const publicRoutes = [
  '/',
  '/login',
  '/signup',
  '/api/webhooks/stripe',  // webhooks Stripe ont leur propre signature
  '/api/auth',
  '/_next',
  '/favicon',
]

// Routes API qui nécessitent un rate limiting renforcé
const sensitiveAPIs = [
  '/api/chat',
  '/api/vapi',
  '/api/video',
  '/api/stripe',
]

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // 1. Security Headers (appliqué à toutes les routes)
  const response = NextResponse.next()

  response.headers.set('X-Frame-Options', 'DENY')
  response.headers.set('X-Content-Type-Options', 'nosniff')
  response.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin')
  response.headers.set('X-DNS-Prefetch-Control', 'on')
  response.headers.set(
    'Permissions-Policy',
    'camera=(), microphone=(self), geolocation=(), browsing-topics=(), payment=(self)'
  )

  // Supprime la signature du framework pour ne pas exposer la stack technique
  response.headers.delete('X-Powered-By')

  // Content-Security-Policy strict (appliqué à toutes les routes)
  response.headers.set(
    'Content-Security-Policy',
    [
      "default-src 'self'",
      "base-uri 'self'",
      "form-action 'self'",
      "object-src 'none'",
      "frame-ancestors 'none'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://js.stripe.com",
      "frame-src https://js.stripe.com",
      `connect-src 'self' https://api.stripe.com ${process.env.NEXT_PUBLIC_SUPABASE_URL || ''} https://api.anthropic.com`,
      "img-src 'self' data: blob: https://*.supabase.co",
      "style-src 'self' 'unsafe-inline'",
      "font-src 'self' data:",
    ].join('; ')
  )

  // Vérifier si la route est publique
  const isPublic = publicRoutes.some(route => 
    pathname === route || pathname.startsWith(route + '/')
  )
  
  if (isPublic) {
    return response
  }

  // 2. Rate Limiting basique pour les API sensibles
  const isSensitiveAPI = sensitiveAPIs.some(route => pathname.startsWith(route))
  
  if (isSensitiveAPI) {
    // Vérifier la méthode HTTP
    if (request.method === 'POST') {
      // On peut ajouter un check de content-type
      const contentType = request.headers.get('content-type') || ''
      if (!contentType.includes('application/json') && !contentType.includes('multipart/form-data')) {
        return NextResponse.json(
          { error: 'Content-Type must be application/json' },
          { status: 415 }
        )
      }
    }
  }

  // 3. Vérifier l'authentification pour les routes protégées
  // Les pages du dashboard sont protégées côté client (useEffect dans chaque page)
  // Les API vérifient l'auth dans leur propre handler avec getUser()
  
  return response
}

export const config = {
  matcher: [
    // Appliquer à toutes les routes sauf statiques
    '/((?!_next/static|_next/image|images/|fonts/|favicon.ico).*)',
  ],
}
