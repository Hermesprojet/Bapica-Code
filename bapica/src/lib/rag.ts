/**
 * RAG multi-agent — adapté à l'API match_agent_knowledge
 * Chaque agent ne voit que ses propres connaissances.
 */

import { createClient, type SupabaseClient } from "@supabase/supabase-js"

// Instanciation paresseuse : le client n'est créé qu'à la première utilisation
// (au runtime), jamais à l'import du module — sinon le build échoue lorsque les
// variables d'environnement Supabase sont absentes ("supabaseUrl is required").
let _supabase: SupabaseClient | null = null
function getSupabase(): SupabaseClient {
  if (!_supabase) {
    _supabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL || "",
      process.env.SUPABASE_SERVICE_ROLE_KEY || ""
    )
  }
  return _supabase
}

// Ids CANONIQUES uniquement — doivent correspondre à `agent.id` (voir agents.ts),
// c'est ce que /api/chat passe à retrieveContext(). Auparavant cette liste
// contenait des alias (vocal/juridique/compta) et des ids fantômes
// (analytics/tendances) : le RAG était donc silencieusement DÉSACTIVÉ pour
// closer, legal et accounting (bloqués par cette garde alors que la route les
// demandait). Aligné sur les ids réels.
export const RAG_ENABLED_AGENTS = new Set([
  "general", "support", "content", "prospection-strategie", "closer",
  "telephone", "accounting", "video", "recruiter", "legal",
])

export async function embed(text: string): Promise<number[]> {
  const res = await fetch("https://api.openai.com/v1/embeddings", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ model: "text-embedding-3-small", input: text }),
  })
  const data = await res.json()
  return data.data[0].embedding
}

export function chunkText(text: string, chunkSize = 500, overlap = 50): string[] {
  const words = text.split(/\s+/)
  const chunks: string[] = []
  for (let i = 0; i < words.length; i += chunkSize - overlap) {
    chunks.push(words.slice(i, i + chunkSize).join(" "))
  }
  return chunks
}

export async function ingestKnowledge(params: {
  text: string; source: string; category: string; agentId: string
}): Promise<{ inserted: number }> {
  const { text, source, category, agentId } = params
  const chunks = chunkText(text)
  let inserted = 0
  for (const chunk of chunks) {
    if (chunk.trim().length < 30) continue
    const embedding = await embed(chunk)
    const { error } = await getSupabase().from("growth_knowledge").insert({
      content: chunk, source, category, agent_id: agentId, embedding,
    })
    if (!error) inserted++
  }
  return { inserted }
}

export async function retrieveContext(question: string, agentId: string): Promise<string> {
  if (!RAG_ENABLED_AGENTS.has(agentId)) return ""
  const queryEmbedding = await embed(question)
  const { data, error } = await getSupabase().rpc("match_agent_knowledge", {
    query_embedding: queryEmbedding,
    filter_agent_id: agentId,
    match_threshold: 0.35,
    match_count: 5,
  })
  if (error || !data?.length) return ""
  return data.map((row: any, i: number) =>
    `[Extrait ${i + 1} — source: ${row.source}]\n${row.content}`
  ).join("\n\n")
}

// Compatibilité avec l'ancien code
export async function searchKnowledge(query: string, userId: string, agentId?: string) {
  const ctx = agentId ? await retrieveContext(query, agentId) : ""
  return ctx ? [{ id: "rag", title: "RAG", content: ctx, category: "rag", agentId: agentId || null, similarity: 1 }] : []
}

export function formatKnowledgeContext(matches: any[]): string {
  if (!matches.length || !matches[0].content) return ""
  return `\n\n--- Connaissances métier ---\n${matches[0].content}\n---\n`
}
