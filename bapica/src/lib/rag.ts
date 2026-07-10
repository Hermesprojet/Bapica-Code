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
 * Découpe un texte long en chunks avec chevauchement
 */
function chunkText(text: string, chunkSize = 500, overlap = 50): string[] {
  const words = text.split(/\s+/)
  const chunks: string[] = []
  for (let i = 0; i < words.length; i += chunkSize - overlap) {
    chunks.push(words.slice(i, i + chunkSize).join(' '))
  }
  return chunks
}

/**
 * Insère une fiche de connaissance avec chunking automatique
 */
export async function insertKnowledge(
  title: string,
  content: string,
  category: string,
  tags: string[] = [],
  agentId?: string
): Promise<number> {
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL || '',
    process.env.SUPABASE_SERVICE_ROLE_KEY || ''
  )

  let inserted = 0
  const chunks = chunkText(content)
  if (chunks.length === 0) chunks.push(content)

  for (const chunk of chunks) {
    if (chunk.trim().length < 30) continue
    try {
      const embedding = await getEmbedding(`${title}\n${chunk}`)
      const { error } = await supabase.from('growth_knowledge').insert({
        title: title + (chunks.length > 1 ? ` (part ${inserted + 1}/${chunks.length})` : ''),
        content: chunk,
        category,
        tags,
        agent_id: agentId || null,
        embedding,
      })
      if (!error) inserted++
    } catch (e) {
      console.error(`Chunk insert failed: ${e}`)
    }
  }
  return inserted
}
