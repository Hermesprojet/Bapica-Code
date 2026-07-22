// Outil « proposer un SMS » — parité Limova (Tom envoie le compte rendu d'appel par SMS,
// au choix). L'agent PROPOSE l'envoi ; le client valide dans « Actions à valider », puis le
// SMS part via Twilio. Idéal pour les comptes rendus d'appel de Hugo et Nadia.

export const proposeSmsTool = {
  name: 'proposer_sms',
  description:
    "PROPOSE l'envoi d'un SMS (compte rendu d'appel, rappel de RDV, notification courte). Tu ne " +
    "l'envoies PAS : il est mis en attente et le client valide d'un clic dans « Actions à valider ». " +
    "Donne le numéro au format international (+33…) et un texte concis (160-320 caractères idéalement).",
  input_schema: {
    type: 'object' as const,
    properties: {
      to: { type: 'string', description: 'Numéro du destinataire au format international (ex : +33612345678)' },
      text: { type: 'string', description: 'Contenu du SMS' },
    },
    required: ['to', 'text'],
  },
}
