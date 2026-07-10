#!/usr/bin/env tsx
/**
 * Test RAG — vérifie que les fiches remontent correctement
 * Usage: npx tsx scripts/test-rag.ts [agent_id]
 */

import { retrieveContext } from "../src/lib/rag"

const TESTS: { agent: string; questions: string[] }[] = [
  { agent: "prospection-strategie", questions: [
    "Comment prospecter une PME dans le BTP ?",
    "Quelle stratégie pour augmenter mon CA de 20% ?",
  ]},
  { agent: "support", questions: [
    "Un client est très en colère, comment je réponds ?",
  ]},
  { agent: "recrutement", questions: [
    "Comment rédiger une fiche de poste pour un commercial ?",
  ]},
  { agent: "juridique", questions: [
    "Quelles sont les règles RGPD pour une PME ?",
  ]},
  { agent: "compta", questions: [
    "Comment améliorer ma trésorerie ?",
  ]},
  { agent: "analytics", questions: [
    "Quels indicateurs suivre pour piloter ma croissance ?",
  ]},
  { agent: "tendances", questions: [
    "Comment organiser ma veille concurrentielle ?",
  ]},
  { agent: "general", questions: [
    "Comment déléguer efficacement ?",
  ]},
]

async function main() {
  const filterAgent = process.argv[2]
  const filtered = filterAgent ? TESTS.filter(t => t.agent === filterAgent) : TESTS

  console.log("=".repeat(60))
  console.log("TEST RAG — Bapica")
  console.log("=".repeat(60))

  for (const { agent, questions } of filtered) {
    for (const q of questions) {
      console.log(`\nAGENT   : ${agent}`)
      console.log(`QUESTION: ${q}`)
      console.log("-".repeat(60))
      
      try {
        const ctx = await retrieveContext(q, agent)
        if (!ctx) {
          console.log("⚠️  Aucune fiche récupérée")
          continue
        }
        
        // Parse et affiche les extraits avec score
        const lines = ctx.split('\n')
        for (const line of lines) {
          if (line.startsWith('[Extrait')) {
            const match = line.match(/source: (.+)\]/)
            if (match) {
              console.log(`✅ ${match[1]}`)
            }
          }
        }
      } catch (e) {
        console.log(`❌ Erreur: ${e}`)
      }
    }
  }
  console.log("\n" + "=".repeat(60))
}

main()
