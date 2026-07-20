/**
 * Base de connaissances de l'assistant d'aide Bapica (« Support Bapica »).
 * Décrit le produit du point de vue CLIENT : où cliquer, comment faire, quoi faire
 * quand ça coince. À tenir à jour quand une fonctionnalité change.
 */
export const SUPPORT_KB = `
BAPICA — GUIDE D'UTILISATION

QU'EST-CE QUE BAPICA
Une plateforme de 10 agents IA spécialisés pour PME et indépendants. Les agents ne se contentent
pas de conseiller : ils agissent (appeler des prospects, répondre aux clients, lire vos données
comptables, préparer des factures). Formules : Essentiel 49 €/mois (8 agents) et Pro 79 €/mois
(10 agents). Essai gratuit 15 jours.

LES 10 AGENTS
- Léo (Agent Général) : point d'entrée, coordonne les autres, gère la to-do.
- Sofia (Support Client) : trie et répond aux emails et messages des clients.
- Camille (Contenu / SEO) : audit SEO, articles, calendrier éditorial, publication réseaux.
- Marc (Croissance & Prospection) : campagnes LinkedIn/phoning, qualification, prise de RDV.
- Nadia (Closer Vocal) : appelle les prospects, traite les objections, résume chaque appel.
- Hugo (Téléphonique) : standard 24/7, qualification, prise de RDV. Formule Pro.
- Claire (Comptabilité) : factures, relances d'impayés, trésorerie, prévisions. Formule Pro.
- Maya (Vidéo IA) : scripts, storyboards et vidéos IA, publication multi-réseaux.
- Yanis (Recrutement) : offres, tri de CV, préparation d'entretiens, documents RH.
- Inès (Juridique) : contrats, CGV, RGPD, analyse de documents reçus.
Remarque : Claire et Hugo n'apparaissent qu'avec la formule Pro. Si un client ne les voit pas,
c'est presque toujours parce qu'il est en formule Essentiel.

NAVIGATION DU TABLEAU DE BORD (menu de gauche)
- Tableau de bord : vue d'ensemble.
- Mes agents : discuter avec un agent (cliquer sur sa carte).
- Prospects : rechercher des contacts B2B.
- Actions à valider : approuver ou refuser les actions préparées par les agents.
- Studio Vidéo : créer des vidéos avec Maya.
- Connaissances : téléverser vos documents pour que les agents connaissent votre entreprise.
- Connexions : relier vos outils (compta, banque, CRM, e-commerce…).
- Canaux : rendre les agents joignables sur WhatsApp, Telegram, Messenger.
- Abonnement : formule et facturation. Paramètres : compte.

COMMENT CONNECTER TELEGRAM (2 minutes)
Canaux → bloc « Telegram — connexion en 1 clic ». Créer un bot avec @BotFather sur Telegram
(commande /newbot), copier le jeton, le coller dans le champ, cliquer Connecter. Bapica valide le
bot et enregistre le webhook automatiquement. Ensuite, écrire au bot : les agents répondent.

COMMENT CONNECTER WHATSAPP
Canaux → carte « WhatsApp (via Twilio) ». Il faut un compte Twilio et le bac à sable WhatsApp pour
tester. Les étapes sont détaillées sur la carte. Une connexion simplifiée (le client garde son
propre numéro, sans passer par Facebook) est en préparation.

COMMENT CONNECTER UN OUTIL (compta, banque, CRM…)
Connexions → chercher la plateforme → Connecter → coller la clé API. Une aide indique où trouver
la clé pour chaque plateforme. Connectables immédiatement : Stripe, Pennylane, Qonto, HubSpot,
Pipedrive, Brevo, Mailchimp, SendGrid, Shopify, Notion, Slack, Calendly, Trello, Asana, Monday,
ClickUp, Mollie, Wise, Zoho.
Certaines plateformes affichent « Bientôt » (Gmail, Outlook, banques hors Qonto…) : elles exigent
une validation de l'éditeur ou un agrégateur bancaire agréé. Survoler le badge indique la raison.
Si votre outil n'est pas dans la liste : bloc « Votre plateforme n'est pas dans la liste ? » en bas
de la page — renseigner le nom, la catégorie, l'URL de l'API et la clé.

CE QUE LES AGENTS PEUVENT FAIRE AVEC VOS OUTILS
- Lecture : ils consultent vos vraies données (clients Stripe, factures Pennylane, transactions
  Qonto, pipeline HubSpot…). Il suffit de leur demander.
- Écriture : ils ne modifient JAMAIS rien tout seuls. Ils préparent l'action, elle apparaît dans
  « Actions à valider », et rien ne part tant que vous n'avez pas cliqué sur Valider. Vous pouvez
  voir le détail technique avant d'approuver, et refuser à tout moment.

RECHERCHER DES PROSPECTS
Menu Prospects (ou depuis Marc/Nadia). Deux sources :
- Hunter — par domaine : saisir le domaine d'une entreprise (ex : exemple.com) pour obtenir les
  personnes et leurs emails. L'offre gratuite Hunter permet environ 25 recherches par mois.
- Apollo — par critères : recherche par poste, lieu, secteur, taille. Attention, l'API de recherche
  d'Apollo nécessite un plan Apollo PAYANT ; avec un compte gratuit, un message l'indique.

APPELS TÉLÉPHONIQUES
Sur la page de Nadia (ou Hugo), le bloc « Lancer un appel » permet de déclencher un appel réel :
numéro, nom du prospect, contexte, puis Appeler. Nécessite un compte Vapi configuré.

DOCUMENTS ET CONNAISSANCE DE L'ENTREPRISE
Connaissances : téléverser des PDF, Word ou texte. Les agents s'appuient dessus pour répondre.
Plus le profil d'entreprise (onboarding) est complet, plus les réponses sont précises : les agents
connaissent secteur, taille, concurrents et objectifs sans avoir à les redemander.

PROBLÈMES COURANTS
- « Un agent n'apparaît pas » : Claire et Hugo demandent la formule Pro.
- « Configuration manquante » ou « en cours de configuration » : la clé du service concerné n'est
  pas encore renseignée. Le message indique laquelle.
- « Plan Apollo » : la recherche par critères exige un abonnement Apollo payant ; utiliser Hunter
  en attendant.
- Une action échoue après validation : le message d'erreur de la plateforme est affiché dans
  l'historique des actions ; il indique la cause (clé invalide, champ manquant…).
- Un agent répond de façon générique : compléter le profil d'entreprise et téléverser des documents.
- Le bot Telegram ne répond pas : vérifier que la connexion est bien affichée comme active dans
  Canaux, et reconnecter le jeton si besoin.
`.trim()
