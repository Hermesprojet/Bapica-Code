/**
 * RAG (Retrieval-Augmented Generation) pour Bapica
 * 
 * Recherche vectorielle dans Supabase pgvector pour enrichir
 * les réponses du Conseiller Croissance avec des connaissances métier.
 */

import { createClient } from '@supabase/supabase-js'

export interface KnowledgeMatch {
  id: string
  title: string
  content: string
  category: string
  agentId: string | null
  similarity: number
}

/**
 * Recherche les connaissances les plus pertinentes, filtrées par agent
 */
export async function searchKnowledge(
  query: string,
  userId: string,
  agentId?: string,
  matchThreshold: number = 0.5,
  maxResults: number = 5
): Promise<KnowledgeMatch[]> {
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL || '',
    process.env.SUPABASE_SERVICE_ROLE_KEY || ''
  )

  const embedding = await getEmbedding(query)

  const { data, error } = await supabase.rpc('search_growth_knowledge', {
    query_embedding: embedding,
    match_threshold: matchThreshold,
    match_count: maxResults,
    agent_filter: agentId || null,
  })

  if (error || !data) return []

  return data.map((row: any) => ({
    id: row.id,
    title: row.title,
    content: row.content,
    category: row.category,
    agentId: row.agent_id || null,
    similarity: row.similarity,
  }))
}

/**
 * Formate les connaissances trouvées pour les injecter dans le prompt Claude
 */
export function formatKnowledgeContext(matches: KnowledgeMatch[]): string {
  if (matches.length === 0) return ''

  return `\n\n--- Connaissances métier pertinentes ---\n${matches
    .map(
      (m, i) =>
        `[${i + 1}] ${m.title} (${m.category}, pertinence: ${Math.round(m.similarity * 100)}%)\n${m.content}`
    )
    .join('\n\n')}\n---\n`
}

/**
 * Génère un embedding via l'API OpenAI
 */
export async function getEmbedding(text: string): Promise<number[]> {
  const apiKey = process.env.OPENAI_API_KEY
  if (!apiKey) throw new Error('OPENAI_API_KEY non configurée')

  const res = await fetch('https://api.openai.com/v1/embeddings', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: 'text-embedding-3-small',
      input: text.slice(0, 8000),
    }),
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(`OpenAI embedding error: ${text}`)
  }

  const json = await res.json()
  return json.data[0].embedding
}

/**
 * Insère une fiche de connaissance dans la base vectorielle
 */
export async function insertKnowledge(
  title: string,
  content: string,
  category: string,
  tags: string[] = []
): Promise<string | null> {
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL || '',
    process.env.SUPABASE_SERVICE_ROLE_KEY || ''
  )

  const embedding = await getEmbedding(`${title}\n${content}`)

  const { data, error } = await supabase
    .from('growth_knowledge')
    .insert({
      title,
      content,
      category,
      tags,
      embedding,
    })
    .select('id')
    .single()

  if (error) {
    console.error('Insert knowledge error:', error)
    return null
  }

  return data.id
}
