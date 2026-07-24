// Outil « proposer une automatisation » — le RÉPÉTABLE délégué à N8N, avec l'accord du client.
// L'agent PROPOSE de transformer une tâche récurrente en automatisation ; elle ne tourne
// qu'après validation du client (page « Automatisations »). À chaque déclenchement planifié,
// l'agent responsable exécute la consigne ; les actions externes restent soumises à validation.

export const proposeAutomationTool = {
  name: 'proposer_automation',
  description:
    "PROPOSE d'automatiser une tâche RÉCURRENTE (relances d'impayés, publication de posts, rapport " +
    "hebdo, veille concurrentielle, résumé de trésorerie mensuel…). Tu ne l'actives PAS : le client la " +
    "valide dans « Automatisations », puis N8N la déclenche selon la planification et l'agent l'exécute " +
    "de façon AUTONOME (envois inclus, puisque le client a donné son accord). Donne un titre, une " +
    "description précise et autoportante de ce qui doit être fait à chaque exécution, une planification " +
    "cron (5 champs, UTC) et son libellé lisible. Précise l'agent le plus adapté si ce n'est pas toi.",
  input_schema: {
    type: 'object' as const,
    properties: {
      title: { type: 'string', description: "Nom de l'automatisation (ex : « Rapport de trésorerie hebdomadaire »)" },
      description: { type: 'string', description: 'Consigne exécutée à chaque déclenchement (précise et autoportante)' },
      cron: { type: 'string', description: 'Planification cron 5 champs en UTC (ex : « 0 7 * * 1 » = lundi 7h UTC)' },
      schedule_label: { type: 'string', description: 'Planification lisible (ex : « chaque lundi à 8h »)' },
      agent_id: { type: 'string', description: "Agent responsable de l'exécution (general, accounting, content…) — optionnel" },
    },
    required: ['title', 'description', 'cron'],
  },
}
