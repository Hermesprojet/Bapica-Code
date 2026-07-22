// Contenu marketing des pages dédiées /agents/[id].
// Chaque entrée complète les données techniques de lib/agents.ts.
// Parité de capacités Limova : les cas d'usage reflètent tout ce que fait l'agent Limova
// de même spécialité (Tom, Charly, Elio, Julia, John, Rony, Lou, Manue).

export interface AgentPageContent {
  tagline: string
  useCases: { title: string; desc: string }[]
  conversation: { role: 'user' | 'assistant'; text: string }[]
  keyResult: string
}

export const AGENT_CONTENT: Record<string, AgentPageContent> = {
  general: {
    tagline: 'Votre point d’entrée universel : Léo lit vos emails, gère votre agenda, rédige vos documents et pilote les autres agents — et répond à n’importe quelle question, 24h/24.',
    useCases: [
      { title: 'Assistant bureautique', desc: 'Emails, agenda, devis PDF, tableaux Excel, présentations : Léo produit, range dans votre cloud et envoie.' },
      { title: 'Analyse de documents', desc: 'Un contrat, une facture, un rapport de 30 pages : l’essentiel extrait et comparé en quelques secondes.' },
      { title: 'Chef d’orchestre', desc: '« Dis à Hugo de… », « demande à Marc de… » : Léo transmet vos consignes et centralise les résultats.' },
    ],
    conversation: [
      { role: 'user', text: 'Je dois annoncer une hausse de tarif à mes clients, comment m’y prendre ?' },
      { role: 'assistant', text: 'Annoncez-la 30 à 60 jours à l’avance, justifiez-la par la valeur ajoutée et proposez de bloquer l’ancien tarif pour tout engagement annuel. Je peux vous rédiger l’email d’annonce tout de suite si vous me donnez votre activité et le pourcentage de hausse.' },
    ],
    keyResult: 'Une équipe entière pilotée depuis une seule conversation, 24h/24.',
  },
  support: {
    tagline: 'Sofia répond à vos clients 24h/24 sur le chat, WhatsApp et par email, à partir de votre base de connaissance, et n’escalade vers vous que ce qui le mérite.',
    useCases: [
      { title: 'Base de connaissance', desc: 'FAQ, fiches produit, tarifs : plus vous la nourrissez, plus Sofia répond juste et vite.' },
      { title: 'Support hors horaires', desc: 'Vos clients sont pris en charge le soir et le week-end, sans embaucher.' },
      { title: 'Étiquetage & escalade', desc: 'Chaque échange trié (question, réclamation, SAV) ; les cas sensibles vous arrivent avec un résumé.' },
    ],
    conversation: [
      { role: 'user', text: 'Bonjour, ma commande n°4521 n’est toujours pas arrivée…' },
      { role: 'assistant', text: 'Bonjour, je comprends votre inquiétude. Votre commande a été expédiée le 12 et l’estimation de livraison est demain avant 18h. Je vous envoie le lien de suivi. Si elle n’est pas livrée demain soir, je déclenche immédiatement une réexpédition ou un remboursement, au choix.' },
    ],
    keyResult: 'Jusqu’à 80 % des demandes résolues sans intervention humaine.',
  },
  content: {
    tagline: 'Camille pilote votre SEO et vos réseaux : audit, articles optimisés, posts adaptés à chaque plateforme — et publie directement sur votre site et vos comptes.',
    useCases: [
      { title: 'Audit SEO complet', desc: 'Votre site et ceux de vos concurrents passés au crible, correctifs priorisés par gain potentiel.' },
      { title: 'Articles & posts publiés', desc: 'Articles de 500 à 3000 mots et posts adaptés à chaque réseau, déposés en brouillon puis publiés (WordPress, Wix, Shopify).' },
      { title: 'Calendrier éditorial', desc: 'Un plan de contenu sur plusieurs mois, programmé aux horaires les plus performants.' },
    ],
    conversation: [
      { role: 'user', text: 'Rédige un post LinkedIn pour présenter mon cabinet de courtage à des primo-accédants.' },
      { role: 'assistant', text: 'Voici une proposition : « Acheter son premier bien en 2026 sans y laisser ses nerfs, c’est possible. Le bon taux ne se trouve pas, il se négocie… » — accroche, 3 conseils concrets, appel à l’action en commentaire. Je vous prépare aussi 2 variantes de ton : experte ou complice ?' },
    ],
    keyResult: 'Un mois de contenu produit et programmé en une après-midi.',
  },
  'prospection-strategie': {
    tagline: 'Marc prospecte pour vous : campagnes LinkedIn et d’appels sortants, prospects analysés, leads qualifiés et rendez-vous posés directement dans votre agenda.',
    useCases: [
      { title: 'Campagnes automatisées', desc: 'LinkedIn (connexions, messages, relances) et appels sortants, dans le respect des limites de chaque plateforme.' },
      { title: 'Leads qualifiés & étiquetés', desc: 'Chaque contact trié (intéressé, à rappeler, hors cible) et le rendez-vous placé dans votre agenda.' },
      { title: 'Diagnostic commercial', desc: 'Taux de réponse et de conversion analysés, correctifs concrets et note de préparation avant vos RDV clés.' },
    ],
    conversation: [
      { role: 'user', text: 'Je vends des logiciels de caisse aux restaurants. Comment aborder un gérant ?' },
      { role: 'assistant', text: 'Approche recommandée : mentionnez un irritant concret (« combien de temps perdez-vous chaque soir sur la clôture de caisse ? »), pas votre produit. Voici un message de 4 lignes personnalisable par type d’établissement, et une relance J+4 orientée témoignage client. Voulez-vous que je décline pour brasseries et restauration rapide ?' },
    ],
    keyResult: 'Un pipeline de prospects qualifiés alimenté chaque semaine.',
  },
  closer: {
    tagline: 'Nadia qualifie vos prospects par téléphone, traite les objections, étiquette chaque appel et convertit les intéressés en rendez-vous dans votre agenda.',
    useCases: [
      { title: 'Qualification vocale', desc: 'Chaque lead entrant est rappelé, qualifié et étiqueté en quelques minutes.' },
      { title: 'Traitement des objections', desc: '« C’est trop cher », « je vais réfléchir » : des réponses préparées et naturelles.' },
      { title: 'Prise de rendez-vous', desc: 'Les prospects chauds atterrissent directement dans votre agenda, avec un résumé d’appel.' },
    ],
    conversation: [
      { role: 'user', text: 'Un prospect me dit toujours « rappelez-moi le mois prochain ». Que faire ?' },
      { role: 'assistant', text: 'C’est une objection de report, pas un refus. Répondez : « Bien sûr. Pour que ce rappel vous soit utile, qu’est-ce qui aura changé le mois prochain ? » Cela révèle le vrai blocage — budget, décideur ou priorité — et vous permet d’y répondre maintenant. Je peux qualifier ce prospect par téléphone si vous me donnez son contexte.' },
    ],
    keyResult: 'Aucun lead entrant ne reste sans rappel.',
  },
  telephone: {
    tagline: 'Hugo tient votre standard 24/7 : il décroche dès la première sonnerie, renseigne à partir de votre base de connaissance, prend les RDV et vous résume chaque appel.',
    useCases: [
      { title: 'Accueil téléphonique 24/7', desc: 'Plus aucun appel manqué, même le soir, le week-end ou en intervention.' },
      { title: 'RDV & étiquetage', desc: 'Prise de rendez-vous dans votre agenda et chaque appel étiqueté (devis, SAV, impayé, rappel).' },
      { title: 'Compte rendu mail ou SMS', desc: 'Qui a appelé, pourquoi, ce qui a été décidé, ce qu’il reste à faire : vous recevez tout.' },
    ],
    conversation: [
      { role: 'user', text: 'Je suis artisan, je perds des chantiers parce que je ne peux pas répondre en journée.' },
      { role: 'assistant', text: 'C’est exactement mon rôle : je réponds à chaque appel, je qualifie la demande (type de travaux, adresse, délai), je propose un créneau de visite dans votre agenda et je vous envoie un résumé par SMS. Vous ne rappelez plus que les clients prêts à signer.' },
    ],
    keyResult: '100 % des appels décrochés, zéro chantier perdu.',
  },
  accounting: {
    tagline: 'Claire pilote vos finances : facturation, relances d’impayés, alertes de trésorerie, prévisions et rapports prêts pour votre expert-comptable.',
    useCases: [
      { title: 'Facturation & relances', desc: 'Factures conformes et relances progressives et courtoises qui préservent la relation client.' },
      { title: 'Alertes & rentabilité', desc: 'Tension de trésorerie, échéances (TVA, URSSAF), rentabilité par client : vous êtes prévenu avant.' },
      { title: 'Prévisions & rapports', desc: 'Trésorerie à 3, 6 et 12 mois en trois scénarios, et récapitulatif mensuel prêt pour votre comptable.' },
    ],
    conversation: [
      { role: 'user', text: 'Un client ne m’a pas payé depuis 45 jours, je n’ose pas le relancer trop fort.' },
      { role: 'assistant', text: 'À 45 jours, une relance ferme mais cordiale s’impose. Je propose : rappel de la facture et de l’échéance dépassée, demande de date de règlement précise, et mention neutre des pénalités prévues aux CGV. Voici le texte prêt à envoyer — souhaitez-vous que je programme la relance suivante à J+7 en cas de silence ?' },
    ],
    keyResult: 'Des délais de paiement réduits sans abîmer la relation client.',
  },
  video: {
    tagline: 'Maya transforme vos idées en visuels 4K et vidéos IA ultra-réalistes — à partir d’un texte ou de vos propres photos, prêts à publier et multilingues.',
    useCases: [
      { title: 'Visuels haute résolution', desc: 'Des images professionnelles jusqu’en 4K, au format de chaque réseau.' },
      { title: 'Vidéos IA & Reels', desc: 'Des vidéos ultra-réalistes à partir d’un texte ou d’une de vos photos (produit, équipe).' },
      { title: 'Publication programmée', desc: 'La même vidéo déclinée par langue et publiée automatiquement sur vos réseaux.' },
    ],
    conversation: [
      { role: 'user', text: 'Je veux une vidéo de 30 secondes pour promouvoir mes soldes d’été.' },
      { role: 'assistant', text: 'Voici le script : accroche sur la remise dans les 3 premières secondes, deux produits phares, urgence sur la date de fin, appel à l’action clair. Format vertical 9:16 recommandé pour les réseaux. Validez le script et je lance la génération avec avatar.' },
    ],
    keyResult: 'Des vidéos professionnelles sans tournage ni monteur.',
  },
  recruiter: {
    tagline: 'Yanis gère votre recrutement de A à Z : offres, tri des CV, entretiens préparés, contrats de travail et intégration de vos nouvelles recrues.',
    useCases: [
      { title: 'Offres & tri des CV', desc: 'Annonces adaptées à chaque plateforme, puis chaque CV évalué et classé selon vos critères.' },
      { title: 'Entretiens préparés', desc: 'Grille d’évaluation, questions sur mesure, mises en situation et mails de convocation.' },
      { title: 'Contrats & onboarding', desc: 'Contrats de travail, documents RH, plan d’intégration et grille de salaire du marché.' },
    ],
    conversation: [
      { role: 'user', text: 'J’ai reçu 60 CV pour mon poste de commercial, je suis noyé.' },
      { role: 'assistant', text: 'Donnez-moi vos 4 critères décisifs — par exemple : expérience terrain, secteur, mobilité, prétentions. Je classe les 60 candidatures en trois groupes (à rencontrer, à creuser, hors cible) avec une justification par profil. Vous n’aurez plus que 8 à 10 entretiens vraiment utiles à mener.' },
    ],
    keyResult: 'Le temps de recrutement divisé par trois.',
  },
  legal: {
    tagline: 'Inès rédige et sécurise vos documents — contrats, NDA, CGV, RGPD —, analyse ceux qu’on vous envoie et rédige vos mises en demeure.',
    useCases: [
      { title: 'Rédaction', desc: 'Contrats, NDA, pactes d’associés, CGV/CGU, mentions légales et politique RGPD adaptées à votre activité.' },
      { title: 'Analyse & négociation', desc: 'Les contrats reçus décryptés, clauses à risque repérées et reformulations prêtes à soumettre.' },
      { title: 'Mises en demeure & conseil', desc: 'Impayés et litiges, droit des sociétés et du travail, veille juridique de votre secteur.' },
    ],
    conversation: [
      { role: 'user', text: 'Un client veut annuler une prestation déjà commencée. Que disent mes CGV ?' },
      { role: 'assistant', text: 'Envoyez-moi vos CGV et je vérifie la clause d’annulation. En général, les prestations entamées sont dues au prorata. Si votre clause est absente ou floue, je vous propose une réponse ferme et diplomatique au client, et une clause corrigée pour vos prochains contrats.' },
    ],
    keyResult: 'Des documents conformes sans honoraires à chaque question.',
  },
}
