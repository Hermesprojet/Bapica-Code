import { createClient, type SupabaseClient } from '@supabase/supabase-js'

// Client Supabase « admin » (service role) réservé au code serveur de confiance
// (webhooks Stripe...). Il contourne les Row Level Security : ne jamais l'exposer
// au navigateur. La clé n'est lue qu'à la première utilisation.
let adminClient: SupabaseClient | null = null

export function getSupabaseAdmin(): SupabaseClient {
  if (!adminClient) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
    const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY || ''
    adminClient = createClient(url, serviceKey, {
      auth: { autoRefreshToken: false, persistSession: false },
    })
  }
  return adminClient
}
