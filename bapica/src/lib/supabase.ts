import { createClient, type SupabaseClient } from '@supabase/supabase-js'

// Instanciation paresseuse : le client Supabase n'est construit qu'à la
// première utilisation (côté navigateur, dans un gestionnaire d'évènement),
// pas à l'import du module. Cela évite que le build/prerendu échoue lorsque
// NEXT_PUBLIC_SUPABASE_URL est absente, car createClient lève une erreur
// « supabaseUrl is required » si l'URL est vide.
let supabaseClient: SupabaseClient | null = null

function getSupabase(): SupabaseClient {
  if (!supabaseClient) {
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
    const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''
    supabaseClient = createClient(supabaseUrl, supabaseAnonKey)
  }
  return supabaseClient
}

export const supabase = new Proxy({} as SupabaseClient, {
  get(_target, prop) {
    return Reflect.get(getSupabase(), prop, getSupabase())
  },
})
