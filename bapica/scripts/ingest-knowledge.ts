#!/usr/bin/env tsx
/**
 * Ingère des fiches de connaissance dans la base RAG
 * Usage: npx tsx scripts/ingest-knowledge.ts <fichier.json> [agent_id]
 */

import { readFileSync } from 'fs'
import { insertKnowledge } from '../src/lib/rag'

interface KnowledgeCard {
  title: string
  content: string
  category: string
  tags?: string[]
  agent_id?: string
}

async function main() {
  const file = process.argv[2]
  const defaultAgent = process.argv[3] || undefined

  if (!file) {
    console.error('Usage: npx tsx scripts/ingest-knowledge.ts <fichier.json> [agent_id]')
    process.exit(1)
  }

  const raw = readFileSync(file, 'utf-8')
  const cards: KnowledgeCard[] = JSON.parse(raw)

  console.log(`Ingestion de ${cards.length} fiches...`)

  let ok = 0
  for (const card of cards) {
    try {
      const agentId = card.agent_id || defaultAgent
      const n = await insertKnowledge(card.title, card.content, card.category, card.tags || [], agentId)
      if (n > 0) {
        ok++
        console.log(`  ✅ ${card.title} (${n} chunks)`)
      } else {
        console.log(`  ❌ ${card.title}`)
      }
    } catch (e) {
      console.log(`  ❌ ${card.title} — ${e}`)
    }
  }

  console.log(`\n${ok}/${cards.length} fiches ingérées.`)
}

main()
