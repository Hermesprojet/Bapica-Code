/**
 * Les pièces d'un projet, vues du navigateur : déposer, lister, revoir,
 * décider, reporter.
 *
 * CE MODULE NE LIT AUCUN DOCUMENT ET NE PROPOSE AUCUNE VALEUR. Le serveur lit
 * (couche texte, OCR, entités et géométrie DXF), propose, et enregistre ;
 * l'écran montre ce qui a été lu, recueille la décision d'une personne, et
 * reporte dans l'étude des valeurs DÉJÀ converties par le serveur dans l'unité
 * de chaque champ. Le modèle structurel d'un DXF se DESSINE ici ; il n'est
 * jamais recalculé.
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
  ModeleStructurel,
  NonReportable,
  Preremplissage,
  ProvenanceDTO,
  StructureDuDocument,
  ValeurExtraite,
} from "@contracts/generated/engine";
import {
  ApiInjoignable, AppelRefuse, SessionExpiree, appelProtege, base,
  type PorteurDeJeton,
} from "@/lib/transport";

export type {
  ChampPrerempli, ConflitDePreremplissage, DecisionExtraction, DocumentDepose,
  DocumentTeleverse, Extraction, ModeleStructurel, NonReportable, Preremplissage,
  ProvenanceDTO, StructureDuDocument, ValeurExtraite,
};

export type SourceDeValeur = Extraction["source_type"];

/**
 * LES SOURCES D'UNE VALEUR, dans l'ordre où le serveur les préfère quand elles
 * concordent : la mesure sur le dessin d'abord, l'OCR en dernier.
 */
export const SOURCES: ReadonlyArray<readonly [SourceDeValeur, string]> = [
  ["geometry", "Géométrie du dessin"],
  ["cad_text", "Texte ou cote du DXF"],
  ["text", "Texte du PDF"],
  ["vision", "Détection visuelle"],
  ["ocr", "OCR"],
];

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

/**
 * Le modèle structurel d'un DXF, tel qu'enregistré avec son analyse. `null`
 * pour un document qui n'en a pas (PDF, DXF sans géométrie lue).
 */
export async function lireStructure(
  porteur: PorteurDeJeton, projectId: string, documentId: string,
): Promise<StructureDuDocument | null> {
  try {
    return await appelProtege<StructureDuDocument>(
      `${projet(projectId)}/documents/${encodeURIComponent(documentId)}/structure`,
      porteur, { methode: "GET", idempotent: true });
  } catch (cause) {
    if (cause instanceof AppelRefuse && cause.statut === 404) return null;
    throw cause;
  }
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
    if (d.source === "$INSUNITS") return `celle du dessin ($INSUNITS = ${d.value})`;
    if (d.source === "declaration_et_cotes") {
      return `le dessin ne déclare pas son unité ; « ${String(d.raw_text ?? "")} » `
        + "et les cotes du dessin la donnent";
    }
    if (d.source === "echelle_de_presentation") {
      const ecrite = (d.written ?? {}) as Record<string, unknown>;
      const fenetre = (d.viewport ?? {}) as Record<string, unknown>;
      return `le dessin ne déclare pas son unité ; l'échelle « ${String(ecrite.text ?? "")} » `
        + `écrite dans la présentation « ${String(d.layout ?? "")} » et sa fenêtre `
        + `(${String(fenetre.drawing_units_per_paper_unit ?? "?")} unités par unité de papier) `
        + "la donnent";
    }
    if (d.source === "echelle_ecrite_et_cotes") {
      const ecrite = (d.written ?? {}) as Record<string, unknown>;
      return `feuille PDF : échelle « ${String(ecrite.text ?? d.scale ?? "")} » écrite sur `
        + `la feuille, confirmée par ${String(d.concordant_dimensions ?? "?")} cote(s) sur `
        + `${String(d.dimensions_read ?? "?")} (nombres lus en ${String(d.dimension_unit ?? "?")})`;
    }
    return `déclarée dans le document : « ${String(d.raw_text ?? "")} »`
      + (d.page ? ` (page ${d.page})` : "");
  }
  return null;
}

type Fondement = Record<string, unknown>;

/**
 * LES ÉLÉMENTS DU MODÈLE qu'une proposition géométrique désigne : la travée et
 * sa poutre, le poteau, les deux axes d'un entraxe. Vide pour une valeur lue
 * dans un texte : elle n'a pas de forme sur le dessin.
 */
export function elementsDe(x: Extraction): string[] {
  if (x.source_type !== "geometry") return [];
  const p = (x.position ?? {}) as Fondement;
  const ids = new Set<string>();
  const element = (p.element ?? {}) as Fondement;
  if (typeof element.id === "string" && !String(element.type).endsWith("_group")
      && element.type !== "grid_spacing" && element.type !== "grid_extent") {
    ids.add(element.id);
  }
  if (typeof p.beam === "string") ids.add(p.beam);
  for (const axe of (Array.isArray(p.axes) ? p.axes : [])) {
    if (typeof axe === "string") ids.add(axe);
  }
  for (const i of (Array.isArray(p.instances) ? p.instances : [])) {
    if (typeof i === "string") ids.add(i);
    else if (i && typeof (i as Fondement).id === "string") ids.add((i as Fondement).id as string);
  }
  return Array.from(ids);
}

function appuiEnClair(a: unknown): string {
  const appui = (a ?? {}) as Fondement;
  if (!appui.support) return "extrémité libre";
  const genre = { poteau: "poteau", voile: "voile", poutre: "poutre" }[
    String(appui.kind)] ?? "appui";
  const nom = appui.mark && appui.mark !== genre ? ` ${appui.mark}` : "";
  return `${genre}${nom}${appui.grid_node ? ` en ${appui.grid_node}` : ""}`;
}

/**
 * COMMENT UNE VALEUR A ÉTÉ MESURÉE SUR LE DESSIN, en une phrase : entre quels
 * appuis, par quelle règle, et ce que les cotes du dessin en disent.
 */
export function deriveeDuDessin(x: Extraction): string | null {
  if (x.source_type !== "geometry") return null;
  const f = (x.basis ?? {}) as Fondement;
  const p = (x.position ?? {}) as Fondement;
  const unite = x.proposed_value.unit ? ` ${x.proposed_value.unit}` : "";
  const morceaux: string[] = [];
  const travee = (p.span ?? null) as Fondement | null;
  if (travee) {
    morceaux.push(x.kind === "beam_clear_span"
      ? `entre les nus de ${appuiEnClair(travee.from)} et de ${appuiEnClair(travee.to)}`
      : `entre les centres de ${appuiEnClair(travee.from)} et de ${appuiEnClair(travee.to)}`);
    morceaux.push(`travée ${travee.index}/${travee.count}`);
    if (f.axis_length !== undefined && f.clear_length !== undefined) {
      morceaux.push(`entre-axes ${f.axis_length}${unite}, nu à nu ${f.clear_length}${unite}`);
    }
  } else if (p.support) {
    morceaux.push(`console depuis le nu de ${appuiEnClair(p.support)}`);
  } else if (f.rule === "largeur_de_bande") {
    morceaux.push(`distance entre les deux faces de la poutre (${String(f.drawn_as ?? "")})`);
  } else if (f.rule === "entraxe_droites_paralleles") {
    morceaux.push("distance entre deux axes parallèles de la grille");
  } else if (Array.isArray(p.instances)) {
    morceaux.push(`${p.count ?? p.instances.length} élément(s) de même section`);
  }
  const regle = { bloc: "bloc", calque: "calque", type_de_ligne: "type de ligne",
                  style: "style de trait appris de la feuille",
                  forme: "forme et position",
                  geometrie: "signature géométrique (axe : bulle, famille, trait-point ; pieu : classe de diamètre)" }[
    String(f.classified_by ?? "")];
  if (regle) morceaux.push(`reconnu par ${regle}`);
  for (const c of (Array.isArray(f.dimensions) ? f.dimensions : []) as Fondement[]) {
    morceaux.push(c.forced_mismatch
      ? `la cote du dessin affiche « ${c.displayed} » et contredit la mesure`
      : `la cote du dessin (« ${c.displayed} ») concorde`);
  }
  return morceaux.length ? morceaux.join(" · ") : null;
}

/** Ce que les AUTRES lectures du document disent de la même grandeur. */
export function confrontations(x: Extraction): { accord: string[]; desaccord: string[] } {
  const f = (x.basis ?? {}) as Fondement;
  const enClairTrace = (t: Fondement) => {
    const source = SOURCES.find(([s]) => s === ({ texte_natif: "text", ocr: "ocr",
      dxf: "cad_text", geometrie: "geometry", vision: "vision" } as Record<string, string>)[
      String(t.method)])?.[1] ?? String(t.method);
    return `${t.value}${t.unit ? " " + t.unit : ""} (${source.toLowerCase()} : `
      + `« ${String(t.raw_text ?? "").slice(0, 80)} »)`;
  };
  return {
    accord: ((f.corroborated_by ?? []) as Fondement[]).map(enClairTrace),
    desaccord: ((f.conflicts_with ?? []) as Fondement[]).map(enClairTrace),
  };
}
