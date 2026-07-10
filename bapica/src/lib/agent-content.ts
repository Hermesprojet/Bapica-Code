// Contenu marketing des pages dédiées /agents/[id].
// Chaque entrée complète les données techniques de lib/agents.ts.

export interface AgentPageContent {
  tagline: string
  useCases: { title: string; desc: string }[]
  conversation: { role: 'user' | 'assistant'; text: string }[]
  keyResult: string
}

export const AGENT_CONTENT: Record<string, AgentPageContent> = {
  general: {
    tagline: 'Votre point d’entrée universel : posez n’importe quelle question, Léo s’en occupe ou vous oriente vers le bon spécialiste.',
    useCases: [
      { title: 'Assistant du quotidien', desc: 'Rédiger un email délicat, résumer un document, préparer une réunion.' },
      { title: 'Conseil business', desc: 'Obtenir un avis structuré sur une décision, un prix, une offre.' },
      { title: 'Aiguillage intelligent', desc: 'Identifier quel agent Bapica peut automatiser votre besoin.' },
    ],
    conversation: [
      { role: 'user', text: 'Je dois annoncer une hausse de tarif à mes clients, comment m’y prendre ?' },
      { role: 'assistant', text: 'Annoncez-la 30 à 60 jours à l’avance, justifiez-la par la valeur ajoutée et proposez de bloquer l’ancien tarif pour tout engagement annuel. Je peux vous rédiger l’email d’annonce tout de suite si vous me donnez votre activité et le pourcentage de hausse.' },
    ],
    keyResult: 'Une réponse utile en quelques secondes, 24h/24.',
  },
  support: {
    tagline: 'Sofia répond à vos clients 24h/24, dans toutes les langues, et n’escalade vers vous que ce qui le mérite.',
    useCases: [
      { title: 'Questions fréquentes', desc: 'Livraison, remboursement, fonctionnement : réponses instantanées et cohérentes.' },
      { title: 'Support hors horaires', desc: 'Vos clients sont pris en charge le soir et le week-end, sans embaucher.' },
      { title: 'Escalade intelligente', desc: 'Les cas complexes ou sensibles vous sont transmis avec un résumé clair.' },
    ],
    conversation: [
      { role: 'user', text: 'Bonjour, ma commande n°4521 n’est toujours pas arrivée…' },
      { role: 'assistant', text: 'Bonjour, je comprends votre inquiétude. Votre commande a été expédiée le 12 et l’estimation de livraison est demain avant 18h. Je vous envoie le lien de suivi. Si elle n’est pas livrée demain soir, je déclenche immédiatement une réexpédition ou un remboursement, au choix.' },
    ],
    keyResult: 'Jusqu’à 80 % des demandes résolues sans intervention humaine.',
  },
  content: {
    tagline: 'Camille produit vos articles SEO, posts réseaux sociaux et newsletters — dans votre ton, à votre rythme.',
    useCases: [
      { title: 'Posts LinkedIn / réseaux', desc: 'Un calendrier de publication régulier qui développe votre visibilité.' },
      { title: 'Articles de blog SEO', desc: 'Des contenus structurés autour des mots-clés de votre marché.' },
      { title: 'Newsletters', desc: 'Des emails que vos abonnés ouvrent et lisent vraiment.' },
    ],
    conversation: [
      { role: 'user', text: 'Rédige un post LinkedIn pour présenter mon cabinet de courtage à des primo-accédants.' },
      { role: 'assistant', text: 'Voici une proposition : « Acheter son premier bien en 2026 sans y laisser ses nerfs, c’est possible. Le bon taux ne se trouve pas, il se négocie… » — accroche, 3 conseils concrets, appel à l’action en commentaire. Je vous prépare aussi 2 variantes de ton : experte ou complice ?' },
    ],
    keyResult: 'Un mois de contenu produit en une après-midi.',
  },
  'prospection-strategie': {
    tagline: 'Marc identifie vos prospects idéaux et rédige des messages d’approche personnalisés qui obtiennent des réponses.',
    useCases: [
      { title: 'Ciblage B2B', desc: 'Définir et qualifier votre client idéal, secteur par secteur.' },
      { title: 'Messages personnalisés', desc: 'Des approches LinkedIn et email adaptées à chaque prospect, pas du copier-coller.' },
      { title: 'Relances structurées', desc: 'Des séquences de suivi qui transforment les silences en rendez-vous.' },
    ],
    conversation: [
      { role: 'user', text: 'Je vends des logiciels de caisse aux restaurants. Comment aborder un gérant ?' },
      { role: 'assistant', text: 'Approche recommandée : mentionnez un irritant concret (« combien de temps perdez-vous chaque soir sur la clôture de caisse ? »), pas votre produit. Voici un message de 4 lignes personnalisable par type d’établissement, et une relance J+4 orientée témoignage client. Voulez-vous que je décline pour brasseries et restauration rapide ?' },
    ],
    keyResult: 'Un pipeline de prospects qualifiés alimenté chaque semaine.',
  },
  closer: {
    tagline: 'Nadia qualifie vos prospects par téléphone, traite les objections et convertit les intéressés en rendez-vous.',
    useCases: [
      { title: 'Qualification vocale', desc: 'Chaque lead entrant est rappelé et qualifié en quelques minutes.' },
      { title: 'Traitement des objections', desc: '« C’est trop cher », « je vais réfléchir » : des réponses préparées et naturelles.' },
      { title: 'Prise de rendez-vous', desc: 'Les prospects chauds atterrissent directement dans votre agenda.' },
    ],
    conversation: [
      { role: 'user', text: 'Un prospect me dit toujours « rappelez-moi le mois prochain ». Que faire ?' },
      { role: 'assistant', text: 'C’est une objection de report, pas un refus. Répondez : « Bien sûr. Pour que ce rappel vous soit utile, qu’est-ce qui aura changé le mois prochain ? » Cela révèle le vrai blocage — budget, décideur ou priorité — et vous permet d’y répondre maintenant. Je peux qualifier ce prospect par téléphone si vous me donnez son contexte.' },
    ],
    keyResult: 'Aucun lead entrant ne reste sans rappel.',
  },
  telephone: {
    tagline: 'Hugo tient votre standard : il répond, renseigne, prend les messages et route les appels importants vers vous.',
    useCases: [
      { title: 'Accueil téléphonique 24/7', desc: 'Plus aucun appel manqué, même en intervention ou en congés.' },
      { title: 'Prise de messages', desc: 'Chaque appel est résumé par écrit : qui, quoi, quelle urgence.' },
      { title: 'Routage intelligent', desc: 'Les urgences vous sont transférées, le reste est traité ou planifié.' },
    ],
    conversation: [
      { role: 'user', text: 'Je suis artisan, je perds des chantiers parce que je ne peux pas répondre en journée.' },
      { role: 'assistant', text: 'C’est exactement mon rôle : je réponds à chaque appel, je qualifie la demande (type de travaux, adresse, délai), je propose un créneau de visite dans votre agenda et je vous envoie un résumé par SMS. Vous ne rappelez plus que les clients prêts à signer.' },
    ],
    keyResult: '100 % des appels décrochés, zéro chantier perdu.',
  },
  accounting: {
    tagline: 'Claire gère vos factures, relance les impayés avec tact et vous donne une vision claire de votre trésorerie.',
    useCases: [
      { title: 'Facturation', desc: 'Création et envoi de factures conformes, sans oubli.' },
      { title: 'Relances d’impayés', desc: 'Des relances progressives et courtoises qui préservent la relation client.' },
      { title: 'Suivi de trésorerie', desc: 'Encaissements, TVA, échéances : un tableau de bord toujours à jour.' },
    ],
    conversation: [
      { role: 'user', text: 'Un client ne m’a pas payé depuis 45 jours, je n’ose pas le relancer trop fort.' },
      { role: 'assistant', text: 'À 45 jours, une relance ferme mais cordiale s’impose. Je propose : rappel de la facture et de l’échéance dépassée, demande de date de règlement précise, et mention neutre des pénalités prévues aux CGV. Voici le texte prêt à envoyer — souhaitez-vous que je programme la relance suivante à J+7 en cas de silence ?' },
    ],
    keyResult: 'Des délais de paiement réduits sans abîmer la relation client.',
  },
  video: {
    tagline: 'Maya transforme vos idées en vidéos avec avatar IA : promotions, Reels, présentations — dans toutes les langues.',
    useCases: [
      { title: 'Vidéos promotionnelles', desc: 'Présentez une offre ou un produit avec un avatar professionnel.' },
      { title: 'Reels & formats courts', desc: 'Des vidéos verticales régulières pour Instagram et TikTok.' },
      { title: 'Vidéos multilingues', desc: 'La même vidéo déclinée automatiquement dans la langue de votre audience.' },
    ],
    conversation: [
      { role: 'user', text: 'Je veux une vidéo de 30 secondes pour promouvoir mes soldes d’été.' },
      { role: 'assistant', text: 'Voici le script : accroche sur la remise dans les 3 premières secondes, deux produits phares, urgence sur la date de fin, appel à l’action clair. Format vertical 9:16 recommandé pour les réseaux. Validez le script et je lance la génération avec avatar.' },
    ],
    keyResult: 'Des vidéos professionnelles sans tournage ni monteur.',
  },
  recruiter: {
    tagline: 'Yanis rédige vos offres, trie les CV et préqualifie les candidats — vous ne rencontrez que les meilleurs.',
    useCases: [
      { title: 'Offres d’emploi attractives', desc: 'Des annonces qui donnent envie aux bons profils de postuler.' },
      { title: 'Tri des candidatures', desc: 'Chaque CV évalué selon vos critères, avec une note argumentée.' },
      { title: 'Préqualification', desc: 'Les candidats prometteurs sont contactés et préqualifiés avant votre entretien.' },
    ],
    conversation: [
      { role: 'user', text: 'J’ai reçu 60 CV pour mon poste de commercial, je suis noyé.' },
      { role: 'assistant', text: 'Donnez-moi vos 4 critères décisifs — par exemple : expérience terrain, secteur, mobilité, prétentions. Je classe les 60 candidatures en trois groupes (à rencontrer, à creuser, hors cible) avec une justification par profil. Vous n’aurez plus que 8 à 10 entretiens vraiment utiles à mener.' },
    ],
    keyResult: 'Le temps de recrutement divisé par trois.',
  },
  legal: {
    tagline: 'Inès prépare vos contrats, CGV et mentions légales, et vous aide à rester conforme au RGPD.',
    useCases: [
      { title: 'Contrats & devis', desc: 'Des documents solides adaptés à votre activité et à vos risques.' },
      { title: 'CGV & mentions légales', desc: 'Les textes obligatoires de votre site, rédigés et à jour.' },
      { title: 'Conformité RGPD', desc: 'Registre, consentements, politique de confidentialité : l’essentiel couvert.' },
    ],
    conversation: [
      { role: 'user', text: 'Un client veut annuler une prestation déjà commencée. Que disent mes CGV ?' },
      { role: 'assistant', text: 'Envoyez-moi vos CGV et je vérifie la clause d’annulation. En général, les prestations entamées sont dues au prorata. Si votre clause est absente ou floue, je vous propose une réponse ferme et diplomatique au client, et une clause corrigée pour vos prochains contrats.' },
    ],
    keyResult: 'Des documents conformes sans honoraires à chaque question.',
  },
  analytics: {
    tagline: 'Tom transforme vos chiffres en décisions : tableaux de bord, tendances et recommandations concrètes.',
    useCases: [
      { title: 'Tableaux de bord', desc: 'Vos indicateurs clés (ventes, marges, acquisition) lisibles en un coup d’œil.' },
      { title: 'Analyse de tendances', desc: 'Ce qui progresse, ce qui décroche, et pourquoi.' },
      { title: 'Recommandations', desc: 'Des actions priorisées, pas seulement des graphiques.' },
    ],
    conversation: [
      { role: 'user', text: 'Mon chiffre d’affaires stagne alors que j’ai plus de clients. Pourquoi ?' },
      { role: 'assistant', text: 'Deux hypothèses à vérifier : un panier moyen en baisse ou une dérive de remises. Envoyez-moi vos ventes des 6 derniers mois : je calcule panier moyen, fréquence d’achat et taux de remise par segment, et je vous dis précisément où agir en premier.' },
    ],
    keyResult: 'Des décisions fondées sur vos données, pas sur l’intuition.',
  },
  trends: {
    tagline: 'Lina surveille les tendances de recherche de votre marché et détecte les opportunités avant vos concurrents.',
    useCases: [
      { title: 'Veille de marché', desc: 'Les recherches qui montent dans votre secteur, semaine après semaine.' },
      { title: 'Opportunités produits', desc: 'Détecter une demande émergente avant qu’elle soit saturée.' },
      { title: 'Saisonnalité', desc: 'Anticiper les pics de demande pour ajuster stock et publicité.' },
    ],
    conversation: [
      { role: 'user', text: 'Je vends des produits de jardinage en ligne. Quelles tendances surveiller ?' },
      { role: 'assistant', text: 'Trois signaux intéressants en ce moment : les recherches sur les potagers surélevés progressent fortement, la récupération d’eau de pluie devient un sujet majeur au printemps, et les demandes « jardinage sans entretien » explosent chez les urbains. Je vous prépare une veille hebdomadaire sur ces trois segments ?' },
    ],
    keyResult: 'Un coup d’avance sur votre marché, chaque semaine.',
  },
}
