// Outil « produire un document » — parité Limova (Charly rédige devis PDF, tableaux
// Excel, notes). L'agent génère un VRAI fichier téléchargeable (pas une action externe :
// aucune validation requise). Le fichier est rangé dans « Documents » du tableau de bord.

export const proposeDocumentTool = {
  name: 'proposer_document',
  description:
    "Génère un document téléchargeable pour le client et le range dans « Documents ». " +
    "Types : 'pdf' (devis, rapport, note — HTML imprimable en PDF), 'excel' ou 'csv' (tableau), " +
    "'word' (vrai fichier .docx), 'powerpoint' (vraie présentation .pptx — chaque titre Markdown # ou ## " +
    "démarre une nouvelle diapositive, les lignes suivantes deviennent des puces), 'markdown', 'text'. " +
    "Pour pdf/word/powerpoint/markdown/text, fournis 'content' en Markdown (titres #, gras **, listes, " +
    "tableaux à pipes). Pour excel/csv, fournis 'columns' (en-têtes) et 'rows' (lignes). " +
    "Après appel, dis au client que le document est prêt dans « Documents » (menu latéral).",
  input_schema: {
    type: 'object' as const,
    properties: {
      kind: { type: 'string', enum: ['pdf', 'excel', 'csv', 'word', 'powerpoint', 'markdown', 'text'], description: 'Type de document' },
      title: { type: 'string', description: 'Titre du document (sert aussi de nom de fichier)' },
      content: { type: 'string', description: 'Corps en Markdown (pour pdf, word, powerpoint, markdown, text)' },
      columns: { type: 'array', items: { type: 'string' }, description: 'En-têtes de colonnes (pour excel/csv)' },
      rows: {
        type: 'array',
        items: { type: 'array', items: { type: ['string', 'number'] } },
        description: 'Lignes de données (pour excel/csv)',
      },
    },
    required: ['kind', 'title'],
  },
}
