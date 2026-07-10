#!/usr/bin/env tsx
/**
 * Ingère des fiches de connaissance dans la base RAG
 * Usage: npx tsx scripts/ingest-knowledge.ts <fichier.json>
 */

import { readFileSync } from 'fs'
import { insertKnowledge } from '../src/lib/rag'

interface KnowledgeCard {
  title: string
  content: string
  category: string
  tags?: string[]
}

async function main() {
  const file = process.argv[2]
  if (!file) {
    console.error('Usage: npx tsx scripts/ingest-knowledge.ts <fichier.json>')
    process.exit(1)
  }

  const raw = readFileSync(file, 'utf-8')
  const cards: KnowledgeCard[] = JSON.parse(raw)

  console.log(`Ingestion de ${cards.length} fiches...`)

  let ok = 0
  for (const card of cards) {
    try {
      const id = await insertKnowledge(card.title, card.content, card.category, card.tags || [])
      if (id) {
        ok++
        console.log(`  ✅ ${card.title}`)
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
