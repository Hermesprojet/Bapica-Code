// Outil « programmer des relances » — parité Limova (Manue/Claire relancent les impayés
// selon un échéancier progressif). Claire ne rédige plus la relance à la demande : elle
// PROGRAMME la série (J+7 amiable → J+15 ferme → J+30 mise en demeure), consultable et
// activable dans « Relances » du tableau de bord.

export const scheduleRemindersTool = {
  name: 'programmer_relances',
  description:
    "Programme un échéancier de relances d'impayé pour un client. Fournis le client, l'email de contact, " +
    "la référence de facture, le montant, et la liste des étapes (relances) avec pour chacune : offset_days " +
    "(jours à partir d'aujourd'hui), stage ('amiable', 'ferme', 'mise_en_demeure'), subject et body (que TU " +
    "rédiges). Échéancier standard recommandé : J+7 amiable, J+15 ferme, J+30 mise en demeure. Les relances " +
    "apparaissent dans « Relances » ; le client les envoie (via « Actions à valider ») ou les annule.",
  input_schema: {
    type: 'object' as const,
    properties: {
      client: { type: 'string', description: 'Nom du client débiteur' },
      contact_email: { type: 'string', description: 'Email destinataire des relances' },
      invoice_ref: { type: 'string', description: 'Référence de la facture' },
      amount: { type: 'number', description: 'Montant dû' },
      currency: { type: 'string', description: 'Devise (défaut EUR)' },
      relances: {
        type: 'array',
        description: 'Étapes de relance',
        items: {
          type: 'object',
          properties: {
            offset_days: { type: 'number', description: "Jours à partir d'aujourd'hui" },
            stage: { type: 'string', enum: ['amiable', 'ferme', 'mise_en_demeure'] },
            subject: { type: 'string', description: "Objet de l'email de relance" },
            body: { type: 'string', description: 'Corps de la relance (rédigé par toi)' },
          },
          required: ['offset_days'],
        },
      },
    },
    required: ['client', 'relances'],
  },
}
