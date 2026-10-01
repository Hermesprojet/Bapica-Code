/**
 * Les pièces d'un projet, vues du navigateur : déposer, lister, revoir,
 * décider, reporter.
 *
 * CE MODULE NE LIT AUCUN DOCUMENT ET NE PROPOSE AUCUNE VALEUR. Le serveur lit
 * (couche texte, OCR, entités DXF), propose, et enregistre ; l'écran montre ce
 * qui a été lu, recueille la décision d'une personne, et reporte dans l'étude
 * des valeurs DÉJÀ converties par le serveur dans l'unité de chaque champ.
 *
 * LA DÉCISION NE PORTE NI NOM NI DATE. Le type généré `DecisionExtraction`
 * n'a pas de place pour eux : le nom vient de l'adhésion, la date du serveur.
 */
import type {
  ChampPrerempli,
  ConflitDePreremplissage,
  DecisionExtraction,
  DocumentDepose,
  DocumentTeleverse,
  Extraction,
  ListeDocuments,
  ListeExtractions,
  NonReportable,
  Preremplissage,
  ProvenanceDTO,
  ValeurExtraite,
} from "@contracts/generated/engine";
import {
  ApiInjoignable, AppelRefuse, SessionExpiree, appelProtege, base,
  type PorteurDeJeton,
} from "@/lib/transport";

export type {
  ChampPrerempli, ConflitDePreremplissage, DecisionExtraction, DocumentDepose,
  DocumentTeleverse, Extraction, NonReportable, Preremplissage, ProvenanceDTO,
  ValeurExtraite,
};

/** Les natures qu'on dépose ici, et leur libellé. La base refuse les autres. */
export const NATURES: ReadonlyArray<readonly [string, string]> = [
  ["architect_drawing", "Plan d'architecte"],
  ["formwork_drawing", "Plan de coffrage"],
  ["cctp", "Cahier des charges (CCTP)"],
  ["other", "Autre pièce"],
];

/** Ce que le sélecteur de fichier propose. Le serveur juge sur les octets. */
export const EXTENSIONS_ACCEPTEES = ".pdf,.dxf,.dwg";

/** Les rôles qui déposent et décident — ceux qui lancent un calcul. */
export const ROLES_DE_SAISIE = ["owner", "admin", "engineer", "validating_engineer"];

const projet = (id: string) => `/v1/projects/${encodeURIComponent(id)}`;

/**
 * `uploadDocument()` : le fichier, tel quel, puis son analyse — dans la même
 * requête. La réponse dit ce qui a été lu et combien de valeurs sont
 * proposées ; les mêmes octets déjà déposés rendent le document existant.
 *
 * PAS `idempotent` : un dépôt rejoué après un 401 est un second dépôt.
 */
export async function uploadDocument(
  porteur: PorteurDeJeton, projectId: string, fichier: File, kind: string,
): Promise<DocumentTeleverse> {
  const parametres = new URLSearchParams({ kind, filename: fichier.name });
  return (await appelProtege<DocumentTeleverse>(
    `${projet(projectId)}/documents?${parametres}`, porteur,
    { methode: "POST", octets: fichier },
  ))!;
}

export async function listDocuments(
  porteur: PorteurDeJeton, projectId: string,
): Promise<DocumentDepose[]> {
  const liste = await appelProtege<ListeDocuments>(
    `${projet(projectId)}/documents`, porteur,
    { methode: "GET", idempotent: true });
  return liste?.documents ?? [];
}

/** Une nouvelle analyse — possible tant qu'aucune valeur n'est proposée. */
export async function reanalyser(
  porteur: PorteurDeJeton, projectId: string, documentId: string,
): Promise<DocumentTeleverse> {
  return (await appelProtege<DocumentTeleverse>(
    `${projet(projectId)}/documents/${encodeURIComponent(documentId)}/analysis`,
    porteur, { methode: "POST" }))!;
}

export async function listExtractions(
  porteur: PorteurDeJeton, projectId: string, documentId?: string,
): Promise<Extraction[]> {
  const suffixe = documentId
    ? `?${new URLSearchParams({ document_id: documentId })}` : "";
  const liste = await appelProtege<ListeExtractions>(
    `${projet(projectId)}/extractions${suffixe}`, porteur,
    { methode: "GET", idempotent: true });
  return liste?.extractions ?? [];
}

/**
 * `confirmExtraction()` : confirmer, corriger ou rejeter. Définitif.
 *
 * PAS `idempotent` : rejouer une décision serait en prendre une seconde — que
 * la base refuserait, mais l'écran n'a pas à le provoquer.
 */
export async function confirmExtraction(
  porteur: PorteurDeJeton, projectId: string, extractionId: string,
  decision: DecisionExtraction,
): Promise<Extraction> {
  return (await appelProtege<Extraction>(
    `${projet(projectId)}/extractions/${encodeURIComponent(extractionId)}/decision`,
    porteur, { methode: "POST", corps: decision }))!;
}

/** Les valeurs DÉCIDÉES, déjà dans l'unité de chaque champ de l'étude. */
export async function prefill(
  porteur: PorteurDeJeton, projectId: string, element?: string,
): Promise<Preremplissage> {
  const suffixe = element?.trim()
    ? `?${new URLSearchParams({ element: element.trim() })}` : "";
  return (await appelProtege<Preremplissage>(
    `${projet(projectId)}/extractions/prefill${suffixe}`, porteur,
    { methode: "GET", idempotent: true }))!;
}

/**
 * Télécharge les octets EXACTS de la pièce, empreinte revérifiée par le
 * serveur. Même chemin que les livrables : un `<a href>` ne sait pas joindre
 * l'`Authorization` que la route exige.
 */
export async function telechargerPiece(
  porteur: PorteurDeJeton, projectId: string, piece: DocumentDepose,
): Promise<void> {
  const jeton = await porteur.jetonUtilisable();
  if (!jeton) throw new SessionExpiree();
  const cible = `${base()}${projet(projectId)}/documents/`
    + `${encodeURIComponent(piece.document_id)}/download`;
  let reponse: Response;
  try {
    reponse = await fetch(cible, { headers: { Authorization: `Bearer ${jeton}` } });
  } catch (cause) {
    throw new ApiInjoignable(cause);
  }
  if (!reponse.ok) {
    throw new AppelRefuse(reponse.status, await reponse.text().catch(() => null));
  }
  //: LE NOM ENREGISTRE AU DEPOT, que la liste porte deja: inutile de le
  //: reconstruire depuis un en-tete.
  const url = URL.createObjectURL(await reponse.blob());
  try {
    const lien = document.createElement("a");
    lien.href = url;
    lien.download = piece.filename;
    lien.click();
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** Une grandeur lisible : « 30 cm », « C30/37 », « 2,5 kN/m² ». */
export function enClairValeur(v: ValeurExtraite | null | undefined): string {
  if (!v) return "—";
  const unite = v.unit ? ` ${v.unit.replace("^2", "²").replace("^3", "³")}` : "";
  return `${v.value}${unite}`;
}

/** D'où vient l'unité d'une proposition, en une phrase. */
export function origineDeLUnite(x: Extraction): string | null {
  const fondement = (x.basis ?? {}) as Record<string, unknown>;
  const base_ = fondement.unit_basis;
  if (base_ === "explicite") return "écrite à côté de la valeur";
  if (base_ === "convention") return "par convention de notation (à vérifier)";
  if (base_ === "absente") return "aucune unité écrite ni déclarée : à préciser en corrigeant";
  if (base_ === "declaration") {
    const d = (fondement.unit_declaration ?? {}) as Record<string, unknown>;
    if (d.source === "$INSUNITS") return `unité du dessin ($INSUNITS = ${d.value})`;
    return `déclarée dans le document : « ${String(d.raw_text ?? "")} »`
      + (d.page ? ` (page ${d.page})` : "");
  }
  return null;
}
