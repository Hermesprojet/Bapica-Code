#!/usr/bin/env tsx
/**
 * Test du RAG — pose des questions types et affiche les fiches remontées
 * Usage: npx tsx scripts/test-rag.ts
 */

import { searchKnowledge, formatKnowledgeContext } from '../src/lib/rag'

const TEST_QUESTIONS = [
  "Comment prospecter une PME dans le BTP ?",
  "Quelle stratégie pour augmenter mon chiffre d'affaires de 20% en 6 mois ?",
  "Comment négocier avec un client allemand ?",
  "Quel prix fixer pour mon offre SaaS ?",
  "Comment réduire mon taux de churn ?",
]

async function main() {
  console.log('Test du RAG Bapica\n')

  for (const question of TEST_QUESTIONS) {
    console.log(`❓ ${question}`)
    try {
      const matches = await searchKnowledge(question, 'test-user', undefined, 0.3, 5)
      if (matches.length === 0) {
        console.log('   ⚠️ Aucun résultat\n')
      } else {
        for (const m of matches) {
          console.log(`   📄 ${m.title} (${m.category}) — ${Math.round(m.similarity * 100)}%`)
        }
        console.log()
      }
    } catch (e) {
      console.log(`   ❌ Erreur: ${e}\n`)
    }
  }
}

main()
