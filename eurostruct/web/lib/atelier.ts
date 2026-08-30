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
  CalculDeProjetRequest,
  CalculEnregistre,
  HistoriqueCalculs,
  ListeProjets,
  Projet,
  ProjetCreation,
} from "@contracts/generated/engine";
import { appelProtege, type PorteurDeJeton } from "@/lib/transport";

export type {
  CalculDeProjetRequest,
  CalculEnregistre,
  HistoriqueCalculs,
  ListeProjets,
  Projet,
  ProjetCreation,
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
