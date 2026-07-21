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
    if (!supabaseUrl || !supabaseAnonKey) {
      // Config absente : NE PAS laisser createClient lever « supabaseUrl is required »,
      // sinon le premier accès côté client fait planter TOUT le rendu React (page
      // blanche sur l'ensemble du site — y compris les pages publiques). On construit
      // un client neutre : les appels réseau échoueront proprement (gérés en try/catch
      // dans l'app) au lieu de casser l'interface. En prod, les variables sont définies.
      if (typeof window !== 'undefined') {
        console.warn('[supabase] NEXT_PUBLIC_SUPABASE_URL / ANON_KEY absentes — client en mode dégradé.')
      }
      supabaseClient = createClient('https://placeholder.supabase.co', 'placeholder-anon-key')
    } else {
      supabaseClient = createClient(supabaseUrl, supabaseAnonKey)
    }
  }
  return supabaseClient
}

export const supabase = new Proxy({} as SupabaseClient, {
  get(_target, prop) {
    return Reflect.get(getSupabase(), prop, getSupabase())
  },
})
