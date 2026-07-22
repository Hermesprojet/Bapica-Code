// Outil « étiqueter un échange » — parité Limova (Tom/Elio taguent chaque appel :
// prospect intéressé, rappel demandé, SAV, impayé…). L'agent persiste l'étiquette,
// consultable et filtrable dans « Étiquettes » du tableau de bord.

export const tagInteractionTool = {
  name: 'etiqueter_echange',
  description:
    "Étiquette l'échange en cours (appel, message, email) pour le retrouver et le filtrer plus tard. " +
    "Utilise-le dès que la nature de l'échange est claire. Valeurs de tag : 'prospect_interesse', " +
    "'rappel_demande', 'sav', 'impaye', 'pas_interesse', 'autre'. Ajoute le contact (nom/numéro/email) " +
    "et une note courte si utile.",
  input_schema: {
    type: 'object' as const,
    properties: {
      tag: {
        type: 'string',
        enum: ['prospect_interesse', 'rappel_demande', 'sav', 'impaye', 'pas_interesse', 'autre'],
        description: "Nature de l'échange",
      },
      contact: { type: 'string', description: 'Nom, numéro ou email de l’interlocuteur (optionnel)' },
      channel: { type: 'string', description: 'Canal : chat, whatsapp, telephone, email… (optionnel)' },
      note: { type: 'string', description: 'Note courte (optionnel)' },
    },
    required: ['tag'],
  },
}
