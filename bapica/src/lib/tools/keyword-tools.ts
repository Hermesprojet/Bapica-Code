// Outil « recherche de mots-clés » — parité Limova (Lou identifie les mots-clés à fort
// potentiel). Camille interroge l'autocomplétion Google pour obtenir les vraies requêtes
// des internautes (longue traîne, questions) autour d'un terme.

export const keywordResearchTool = {
  name: 'rechercher_motscles',
  description:
    "Recherche RÉELLE de mots-clés autour d'un terme (via l'autocomplétion Google) : renvoie les " +
    "requêtes réellement tapées par les internautes — longue traîne, questions, intentions d'achat. " +
    "Utilise-le pour bâtir une stratégie SEO, un calendrier éditorial ou choisir l'angle d'un article, " +
    "AVANT de rédiger. Fournis un mot-clé de départ et la langue.",
  input_schema: {
    type: 'object' as const,
    properties: {
      seed: { type: 'string', description: 'Mot-clé ou expression de départ (ex : « logiciel de caisse »)' },
      lang: { type: 'string', description: 'Langue (fr, en…) — défaut fr' },
    },
    required: ['seed'],
  },
}
