#!/usr/bin/env tsx
import { readFileSync } from "fs"
import { ingestKnowledge } from "../src/lib/rag"

interface KnowledgeItem {
  agent_id?: string
  source: string
  category: string
  content: string
}

const DEFAULT_AGENT = "prospection-strategie"

async function main() {
  const filePath = process.argv[2]
  if (!filePath) {
    console.error("Usage: npx tsx scripts/ingest-knowledge.ts <fichier.json>")
    process.exit(1)
  }

  const items: KnowledgeItem[] = JSON.parse(readFileSync(filePath, "utf-8"))
  console.log(`${items.length} fiches à ingérer...`)

  let total = 0
  for (const item of items) {
    const agentId = item.agent_id ?? DEFAULT_AGENT
    const { inserted } = await ingestKnowledge({
      text: item.content,
      source: item.source,
      category: item.category,
      agentId,
    })
    total += inserted
    console.log(`  ✓ [${agentId}] ${item.source} (${inserted} chunk(s))`)
  }

  console.log(`\nTerminé. ${total} chunk(s) insérés.`)
}

main().catch((err) => {
  console.error("Erreur:", err)
  process.exit(1)
})
