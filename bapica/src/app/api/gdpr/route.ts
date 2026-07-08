import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

async function corsHeaders() {
  return {
    'Access-Control-Allow-Origin': 'https://bapica.com',
    'Access-Control-Allow-Methods': 'POST, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  }
}

export async function OPTIONS() {
  return NextResponse.json({}, { headers: await corsHeaders() })
}

// POST /api/gdpr/delete
// Body: { confirmation: "SUPPRIMER" }
// Supprime toutes les données d'un utilisateur (droit à l'oubli RGPD)
export async function POST(req: NextRequest) {
  try {
    const supabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL || '',
      process.env.SUPABASE_SERVICE_ROLE_KEY || '',
      { auth: { persistSession: false, autoRefreshToken: false } }
    )

    // Vérifier l'authentification
    const { data: { user }, error: authError } = await supabase.auth.getUser()
    if (authError || !user) {
      return NextResponse.json({ error: 'Non authentifié' }, { status: 401, headers: await corsHeaders() })
    }

    const { confirmation } = await req.json()
    if (confirmation !== 'SUPPRIMER') {
      return NextResponse.json({ 
        error: 'Envoyez { "confirmation": "SUPPRIMER" } pour confirmer la suppression définitive.' 
      }, { status: 400, headers: await corsHeaders() })
    }

    const userId = user.id

    // Supprimer toutes les données associées
    const results = await Promise.allSettled([
      supabase.from('conversations').delete().eq('user_id', userId),
      supabase.from('api_keys').delete().eq('user_id', userId),
      supabase.from('usage_logs').delete().eq('user_id', userId),
      supabase.from('subscriptions').delete().eq('user_id', userId),
      supabase.from('profiles').delete().eq('id', userId),
      // Supprimer l'utilisateur auth (nécessite service_role)
      supabase.auth.admin.deleteUser(userId),
    ])

    const allOk = results.every(r => r.status === 'fulfilled')
    
    return NextResponse.json({
      success: allOk,
      message: allOk 
        ? 'Toutes vos données ont été supprimées définitivement. Votre compte n\'existe plus.'
        : 'Certaines données n\'ont pas pu être supprimées. Contactez dpo@bapica.com.',
    }, { headers: await corsHeaders() })

  } catch (error) {
    console.error('GDPR delete error:', error)
    return NextResponse.json(
      { error: 'Erreur lors de la suppression des données.' },
      { status: 500, headers: await corsHeaders() }
    )
  }
}

// GET /api/gdpr/export
// Exporte toutes les données personnelles (droit d'accès RGPD)
export async function GET(req: NextRequest) {
  try {
    const supabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL || '',
      process.env.SUPABASE_SERVICE_ROLE_KEY || '',
      { auth: { persistSession: false, autoRefreshToken: false } }
    )

    const { data: { user }, error: authError } = await supabase.auth.getUser()
    if (authError || !user) {
      return NextResponse.json({ error: 'Non authentifié' }, { status: 401, headers: await corsHeaders() })
    }

    const userId = user.id

    // Récupérer toutes les données de l'utilisateur
    const [profile, conversations, usage] = await Promise.all([
      supabase.from('profiles').select('*').eq('id', userId).single(),
      supabase.from('conversations').select('id, agent_id, title, created_at').eq('user_id', userId).order('created_at', { ascending: false }),
      supabase.from('usage_logs').select('*').eq('user_id', userId).order('created_at', { ascending: false }).limit(100),
    ])

    const exportData = {
      exportedAt: new Date().toISOString(),
      profile: profile.data,
      conversations: conversations.data || [],
      recentUsage: usage.data || [],
      note: 'Conformément à l\'article 15 du RGPD, vous avez droit d\'accéder à vos données personnelles.',
    }

    return NextResponse.json(exportData, { headers: await corsHeaders() })

  } catch (error) {
    console.error('GDPR export error:', error)
    return NextResponse.json(
      { error: 'Erreur lors de l\'export des données.' },
      { status: 500, headers: await corsHeaders() }
    )
  }
}
