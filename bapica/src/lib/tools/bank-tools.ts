// Outil « lire la banque » — parité Limova (Manue se branche à la banque pour surveiller
// la trésorerie). Claire lit les soldes et transactions réels via la banque connectée
// du client (GoCardless Bank Account Data, lecture seule).

export const readBankTool = {
  name: 'lire_banque',
  description:
    "Lit les données bancaires RÉELLES du client via sa banque connectée (soldes et transactions " +
    "récentes) — lecture seule. Utilise 'soldes' pour la trésorerie disponible, 'transactions' pour " +
    "l'analyse des flux. Si aucune banque n'est connectée, explique-le et invite à la connecter (Connexions).",
  input_schema: {
    type: 'object' as const,
    properties: {
      action: { type: 'string', enum: ['soldes', 'transactions'], description: 'Donnée à lire' },
    },
    required: ['action'],
  },
}
