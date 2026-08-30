/**
 * L'atelier vu du navigateur : projets, calcul enregistré, historique.
 *
 * AUCUNE FORME N'EST REDÉFINIE ICI
 * ---------------------------------
 * `Projet`, `ProjetCreation`, `CalculEnregistre` et les autres viennent du
 * contrat **généré** depuis les modèles Pydantic. Les recopier créerait une
 * seconde définition qui dériverait au premier champ renommé — et l'un de ces
 * champs décide dans quelle organisation un projet est créé.
 *
 * AUCUN CORPS NE NOMME UNE ORGANISATION, SAUF UNE FOIS ET SOUS CONTRÔLE
 * ----------------------------------------------------------------------
 * `organization_id` n'apparaît que dans `ProjetCreation`, il est facultatif, et
 * PostgreSQL le confronte aux appartenances avant d'en faire quoi que ce soit.
 * Il sert au seul cas où l'ingénieur appartient à plusieurs bureaux. Partout
 * ailleurs, « mon organisation » est une question dont la réponse est en base.
 *
 * TOUS CES APPELS SONT PROTÉGÉS
 * ------------------------------
 * Un projet nomme un client et une adresse ; un calcul porte des nombres
 * qu'un bureau d'études ne publie pas. Contrairement à `lib/api.ts` — dont les
 * appels sont publics parce que le calcul exploratoire est le même pour tout le
 * monde — chacun d'eux porte le jeton, et le serveur en tire l'identité.
 */
import type {
  AttestationDemande,
  CalculDeProjetRequest,
  CalculEnregistre,
  HistoriqueCalculs,
  ListeLivrables,
  ListeProjets,
  Livrable,
  LivrableCreation,
  LivrableDetail,
  Projet,
  ProjetCreation,
  RetourAuBrouillon,
  Transition,
} from "@contracts/generated/engine";
import {
  ApiInjoignable, AppelRefuse, appelProtege, base, SessionExpiree,
  type PorteurDeJeton,
} from "@/lib/transport";

export type {
  AttestationDemande,
  CalculDeProjetRequest,
  CalculEnregistre,
  HistoriqueCalculs,
  ListeLivrables,
  ListeProjets,
  Livrable,
  LivrableCreation,
  LivrableDetail,
  Projet,
  ProjetCreation,
  RetourAuBrouillon,
  Transition,
};

/**
 * Les projets des organisations de l'appelant.
 *
 * IDEMPOTENT: c'est une lecture. Elle peut être rejouée après un 401 sans rien
 * créer — ce que la création, elle, ne peut pas, et ne dit donc pas.
 */
export async function listerProjets(
  porteur: PorteurDeJeton,
): Promise<Projet[]> {
  const liste = await appelProtege<ListeProjets>(
    "/v1/projects", porteur, { methode: "GET", idempotent: true },
  );
  return liste?.projects ?? [];
}

/**
 * Crée un projet et rend **le projet**, pas son identifiant.
 *
 * Le serveur le relit dans la même requête : sans cela l'écran devrait le
 * reconstruire de son côté en attendant un second appel, et afficherait des
 * champs que la base n'a pas confirmés — à commencer par l'organisation.
 */
export async function creerProjet(
  porteur: PorteurDeJeton,
  brouillon: ProjetCreation,
): Promise<Projet> {
  const cree = await appelProtege<Projet>(
    "/v1/projects", porteur, { methode: "POST", corps: brouillon },
  );
  if (!cree?.project_id) {
    // 201 SANS IDENTIFIANT N'EST PAS UNE CRÉATION. On refuse plutôt que
    // d'afficher un projet vide dont personne ne pourra rien faire.
    throw new Error("la creation n'a rendu aucun projet.");
  }
  return cree;
}

/**
 * Lance le calcul **et l'enregistre**, en une requête.
 *
 * DEUX APPELS SÉPARÉS SERAIENT UN DÉFAUT, PAS UNE COMMODITÉ. « Calcule » puis
 * « enregistre ce résultat » laisserait le navigateur choisir ce qui est
 * sauvegardé, et un client pourrait enregistrer des nombres que le moteur n'a
 * jamais produits.
 *
 * LE CORPS NE NOMME AUCUN RÉFÉRENTIEL, et le type l'impose : ni `project_id`,
 * ni `country`, ni `region`, ni `as_of`. Les quatre sont figés sur le projet
 * et lus côté serveur. L'écran ne peut donc pas les envoyer, même par erreur —
 * et s'il le tentait, le contrat `extra="forbid"` répondrait 422.
 */
export async function calculerEtEnregistrer(
  porteur: PorteurDeJeton,
  projectId: string,
  requete: CalculDeProjetRequest,
): Promise<CalculEnregistre> {
  const enregistre = await appelProtege<CalculEnregistre>(
    `/v1/projects/${encodeURIComponent(projectId)}/calculations/ec2/beam-flexure`,
    porteur, { methode: "POST", corps: requete },
  );
  if (!enregistre?.calculation_id) {
    throw new Error("le calcul n'a rendu aucun identifiant.");
  }
  return enregistre;
}

/** L'historique d'un projet, du plus récent au plus ancien. Les refus compris. */
export async function historiqueDuProjet(
  porteur: PorteurDeJeton,
  projectId: string,
): Promise<HistoriqueCalculs> {
  const h = await appelProtege<HistoriqueCalculs>(
    `/v1/projects/${encodeURIComponent(projectId)}/calculations`,
    porteur, { methode: "GET", idempotent: true },
  );
  return h ?? { project_id: projectId, calculations: [] };
}

/**
 * Rouvre un calcul sauvegardé : les MÊMES entrées, les MÊMES résultats.
 *
 * RIEN N'EST RECALCULÉ. Le serveur rend ce qui a été enregistré ; relancer le
 * moteur donnerait le résultat d'aujourd'hui pour un calcul d'hier, avec le
 * code d'aujourd'hui et l'état d'aujourd'hui du référentiel national.
 */
export async function rouvrirCalcul(
  porteur: PorteurDeJeton,
  projectId: string,
  calculationId: string,
): Promise<CalculEnregistre> {
  const relu = await appelProtege<CalculEnregistre>(
    `/v1/projects/${encodeURIComponent(projectId)}/calculations/` +
    `${encodeURIComponent(calculationId)}`,
    porteur, { methode: "GET", idempotent: true },
  );
  if (!relu?.calculation_id) {
    throw new Error("la relecture n'a rendu aucun calcul.");
  }
  return relu;
}

/**
 * Télécharge la note HTML d'un calcul sauvegardé.
 *
 * ELLE PASSE PAR `fetch` ET NON PAR UN LIEN, et c'est nécessaire : la route
 * exige un `Authorization`, qu'un `<a href>` ne sait pas joindre. Un lien
 * direct partirait sans jeton et rendrait 401 — ou pire, obligerait à mettre
 * le jeton dans l'URL, où il finirait dans l'historique du navigateur et dans
 * les journaux du serveur.
 *
 * LE DOCUMENT NE PASSE PAR AUCUN RENDU. Il est reçu tel quel et enregistré tel
 * quel : ce que l'ingénieur archive est exactement ce que le serveur a produit
 * depuis les données gelées.
 */
export async function telechargerNote(
  porteur: PorteurDeJeton,
  projectId: string,
  calculationId: string,
): Promise<void> {
  const jeton = await porteur.jetonUtilisable();
  if (!jeton) throw new SessionExpiree();
  const cible = `${base()}/v1/projects/${encodeURIComponent(projectId)}`
    + `/calculations/${encodeURIComponent(calculationId)}/note.html`;

  let reponse: Response;
  try {
    reponse = await fetch(cible, { headers: { Authorization: `Bearer ${jeton}` } });
  } catch (cause) {
    throw new ApiInjoignable(cause);
  }
  if (!reponse.ok) {
    throw new AppelRefuse(reponse.status, await reponse.text().catch(() => null));
  }

  // LE NOM DE FICHIER VIENT DU SERVEUR quand il le donne. C'est lui qui sait
  // quel repère et quel identifiant le document porte, et il l'a déjà filtré.
  const disposition = reponse.headers.get("content-disposition") ?? "";
  const trouve = /filename="([^"]+)"/.exec(disposition);
  const nom = trouve?.[1] ?? `note-${calculationId}.html`;

  const contenu = await reponse.blob();
  const url = URL.createObjectURL(contenu);
  try {
    const lien = document.createElement("a");
    lien.href = url;
    lien.download = nom;
    lien.click();
  } finally {
    // L'URL D'OBJET EST LIBEREE, TOUJOURS. Sans cela chaque téléchargement
    // retient son blob en mémoire jusqu'au rechargement de la page.
    URL.revokeObjectURL(url);
  }
}

/* ===========================================================================
 * LES LIVRABLES ET LEUR PARCOURS DE RELECTURE
 *
 * TOUS CES APPELS SONT PROTÉGÉS, ET AUCUN NE NOMME UNE IDENTITÉ. Le corps
 * d'une attestation ne porte que ce que le validateur écrit : son nom, son
 * rôle et son numéro d'inscription sortent de son adhésion, côté serveur. Le
 * type généré l'impose — il n'y a aucun champ où les mettre.
 *
 * LES LECTURES SONT `idempotent`, LES ACTIONS NE LE SONT PAS. Rejouer une
 * lecture après un 401 ne crée rien ; rejouer une soumission à la relecture ou
 * une attestation, si. La distinction est portée ici parce que c'est ici
 * qu'elle est connue.
 * =========================================================================== */

/** Les livrables du projet, du plus récent au plus ancien. */
export async function listerLivrables(
  porteur: PorteurDeJeton,
  projectId: string,
): Promise<Livrable[]> {
  const liste = await appelProtege<ListeLivrables>(
    `/v1/projects/${encodeURIComponent(projectId)}/deliverables`,
    porteur, { methode: "GET", idempotent: true },
  );
  return liste?.deliverables ?? [];
}

/** Un livrable, son contexte figé, son attestation et son historique. */
export async function relireLivrable(
  porteur: PorteurDeJeton,
  projectId: string,
  deliverableId: string,
): Promise<LivrableDetail> {
  const relu = await appelProtege<LivrableDetail>(
    `/v1/projects/${encodeURIComponent(projectId)}/deliverables/`
    + `${encodeURIComponent(deliverableId)}`,
    porteur, { methode: "GET", idempotent: true },
  );
  if (!relu?.deliverable_id) {
    throw new Error("la relecture n'a rendu aucun livrable.");
  }
  return relu;
}

/**
 * Produit un brouillon depuis un calcul enregistré.
 *
 * LE NAVIGATEUR N'ENVOIE QU'UN IDENTIFIANT DE CALCUL. Le document est composé
 * sur le serveur à partir des données gelées, ses octets sont déposés, relus
 * et vérifiés avant qu'une ligne ne soit écrite. Rien de tout cela ne peut
 * être influencé d'ici, et c'est le point.
 */
export async function creerLivrable(
  porteur: PorteurDeJeton,
  projectId: string,
  brouillon: LivrableCreation,
): Promise<LivrableDetail> {
  const cree = await appelProtege<LivrableDetail>(
    `/v1/projects/${encodeURIComponent(projectId)}/deliverables`,
    porteur, { methode: "POST", corps: brouillon },
  );
  if (!cree?.deliverable_id) {
    throw new Error("la creation n'a rendu aucun livrable.");
  }
  return cree;
}

/**
 * Émet l'indice suivant, qui remplace celui-ci.
 *
 * C'EST LE SEUL MOYEN DE CORRIGER APRÈS ATTESTATION. Un livrable validé ou
 * émis ne se modifie plus — la base le refuse — et c'est la seule façon qu'une
 * attestation garde un sens.
 */
export async function reviserLivrable(
  porteur: PorteurDeJeton,
  projectId: string,
  deliverableId: string,
  brouillon: LivrableCreation,
): Promise<LivrableDetail> {
  const cree = await appelProtege<LivrableDetail>(
    `/v1/projects/${encodeURIComponent(projectId)}/deliverables/`
    + `${encodeURIComponent(deliverableId)}/revision`,
    porteur, { methode: "POST", corps: brouillon },
  );
  if (!cree?.deliverable_id) {
    throw new Error("la revision n'a rendu aucun livrable.");
  }
  return cree;
}

/** Soumet le brouillon à la relecture. Il reste non opposable. */
export async function soumettreALaRelecture(
  porteur: PorteurDeJeton,
  projectId: string,
  deliverableId: string,
): Promise<LivrableDetail> {
  return (await appelProtege<LivrableDetail>(
    `/v1/projects/${encodeURIComponent(projectId)}/deliverables/`
    + `${encodeURIComponent(deliverableId)}/review`,
    porteur, { methode: "POST", corps: {} },
  ))!;
}

/** Renvoie la pièce au brouillon, avec le motif. Le serveur l'exige non vide. */
export async function renvoyerAuBrouillon(
  porteur: PorteurDeJeton,
  projectId: string,
  deliverableId: string,
  motif: RetourAuBrouillon,
): Promise<LivrableDetail> {
  return (await appelProtege<LivrableDetail>(
    `/v1/projects/${encodeURIComponent(projectId)}/deliverables/`
    + `${encodeURIComponent(deliverableId)}/draft`,
    porteur, { methode: "POST", corps: motif },
  ))!;
}

/**
 * Enregistre l'attestation métier authentifiée, et valide la pièce.
 *
 * CE N'EST PAS UNE SIGNATURE ÉLECTRONIQUE QUALIFIÉE, et l'écran ne l'appelle
 * jamais ainsi. Ce qui est enregistré : un membre actif, nommé par son
 * adhésion, porteur du rôle de validation, atteste avoir relu ce calcul-là.
 */
export async function attesterLivrable(
  porteur: PorteurDeJeton,
  projectId: string,
  deliverableId: string,
  attestation: AttestationDemande,
): Promise<LivrableDetail> {
  return (await appelProtege<LivrableDetail>(
    `/v1/projects/${encodeURIComponent(projectId)}/deliverables/`
    + `${encodeURIComponent(deliverableId)}/validation`,
    porteur, { methode: "POST", corps: attestation },
  ))!;
}

/** Émet le livrable. Impossible sans attestation nominative préalable. */
export async function emettreLivrable(
  porteur: PorteurDeJeton,
  projectId: string,
  deliverableId: string,
): Promise<LivrableDetail> {
  return (await appelProtege<LivrableDetail>(
    `/v1/projects/${encodeURIComponent(projectId)}/deliverables/`
    + `${encodeURIComponent(deliverableId)}/final`,
    porteur, { methode: "POST", corps: {} },
  ))!;
}

/**
 * Télécharge les octets **exacts** du livrable.
 *
 * MÊME CHEMIN QUE LA NOTE, ET POUR LA MÊME RAISON : la route exige un
 * `Authorization` qu'un `<a href>` ne sait pas joindre. Ce qui diffère, c'est
 * ce qui est servi — non pas un document recomposé, mais les octets lus dans
 * le magasin, dont le serveur revérifie l'empreinte avant de les rendre.
 */
export async function telechargerLivrable(
  porteur: PorteurDeJeton,
  projectId: string,
  deliverableId: string,
): Promise<void> {
  const jeton = await porteur.jetonUtilisable();
  if (!jeton) throw new SessionExpiree();
  const cible = `${base()}/v1/projects/${encodeURIComponent(projectId)}`
    + `/deliverables/${encodeURIComponent(deliverableId)}/download`;

  let reponse: Response;
  try {
    reponse = await fetch(cible, { headers: { Authorization: `Bearer ${jeton}` } });
  } catch (cause) {
    throw new ApiInjoignable(cause);
  }
  if (!reponse.ok) {
    throw new AppelRefuse(reponse.status, await reponse.text().catch(() => null));
  }

  const disposition = reponse.headers.get("content-disposition") ?? "";
  const trouve = /filename="([^"]+)"/.exec(disposition);
  const nom = trouve?.[1] ?? `livrable-${deliverableId}.html`;

  const contenu = await reponse.blob();
  const url = URL.createObjectURL(contenu);
  try {
    const lien = document.createElement("a");
    lien.href = url;
    lien.download = nom;
    lien.click();
  } finally {
    URL.revokeObjectURL(url);
  }
}
