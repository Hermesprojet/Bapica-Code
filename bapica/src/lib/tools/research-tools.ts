// Outils de recherche live — donnent aux agents un avantage sur Limova :
// - rechercher_web : recherche internet en temps réel (tous agents).
// - analyser_entreprise : profil factuel d'une société (site + web) — prospection, RDV, recrutement.
// - trouver_prospects : contacts B2B réels (Apollo par critères, Hunter par domaine).

export const webSearchTool = {
  name: 'rechercher_web',
  description:
    "Recherche RÉELLE sur internet en temps réel (actualités, données, concurrents, réglementation, " +
    "salaires, tendances). Utilise-le dès qu'une information à jour est nécessaire au lieu de rester vague " +
    "ou de dire que tu n'as pas accès au web.",
  input_schema: {
    type: 'object' as const,
    properties: { query: { type: 'string', description: 'Requête de recherche' } },
    required: ['query'],
  },
}

export const analyzeCompanyTool = {
  name: 'analyser_entreprise',
  description:
    "Établit un profil factuel d'une entreprise à partir de son site web et de recherches internet " +
    "(activité, positionnement, actualités, taille estimée). Idéal AVANT un rendez-vous, pour qualifier " +
    "un prospect, préparer une approche commerciale ou un recrutement.",
  input_schema: {
    type: 'object' as const,
    properties: {
      companyName: { type: 'string', description: "Nom de l'entreprise" },
      website: { type: 'string', description: 'Site web (optionnel)' },
      sector: { type: 'string', description: 'Secteur (optionnel)' },
      city: { type: 'string', description: 'Ville (optionnel)' },
    },
    required: ['companyName'],
  },
}

export const findProspectsTool = {
  name: 'trouver_prospects',
  description:
    "Recherche des prospects RÉELS. Trois modes : (1) LOCAL — établissements d'un secteur dans une " +
    "ville (sector + city, ex : « plombier » + « Lyon ») via Google Maps/Apify : renvoie nom, " +
    "TÉLÉPHONE, site, note — idéal pour les TPE/commerces/artisans ; (2) B2B par critères (titles = " +
    "postes, locations, keywords) via Apollo ; (3) par domaine d'entreprise (domain, ex : « acme.com ») " +
    "via Hunter. Choisis le mode LOCAL dès qu'il s'agit de prospects de proximité (secteur + ville). " +
    "Réservé à la prospection commerciale.",
  input_schema: {
    type: 'object' as const,
    properties: {
      sector: { type: 'string', description: "Secteur/type d'établissement pour une recherche LOCALE Google Maps (ex : « restaurant », « garage »)" },
      city: { type: 'string', description: 'Ville/zone pour la recherche LOCALE (ex : « Marseille »)' },
      titles: { type: 'array', items: { type: 'string' }, description: 'Postes ciblés (ex : « CEO », « Directeur marketing »)' },
      locations: { type: 'array', items: { type: 'string' }, description: 'Lieux (ex : « Paris, France »)' },
      keywords: { type: 'string', description: 'Mots-clés (secteur, techno…)' },
      domain: { type: 'string', description: "Domaine d'entreprise pour une recherche Hunter (ex : acme.com)" },
    },
    required: [] as string[],
  },
}
