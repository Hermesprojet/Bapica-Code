/**
 * Le client de l'API, typé par le contrat GÉNÉRÉ.
 *
 * CE QUE CE MODULE NE FAIT PAS
 * -----------------------------
 * Il ne redéfinit aucune forme. `Ec2BeamFlexureRequest`, `EngineErrorDTO` et
 * les autres viennent de `packages/contracts/src/generated/engine.ts`, produit
 * depuis les schémas Pydantic du moteur. Recopier une interface ici créerait
 * une seconde définition, qui dériverait au premier changement du moteur — et
 * l'interface afficherait alors des champs qui n'existent plus.
 *
 * IL NE CALCULE RIEN NON PLUS. Aucune formule, aucun arrondi, aucune règle
 * d'ingénierie. L'interface affiche ce que le moteur a décidé.
 */
import type {
  BeamSectionDrawingRequest,
  BlockingParameterDTO,
  Ec2BeamFlexureRequest,
  Ec2BeamFlexureResponse,
  EngineErrorDTO,
} from "@contracts/generated/engine";

/**
 * La réponse de calcul, augmentée des deux champs que la couche HTTP ajoute.
 *
 * `signable` et `mention` ne sont pas des données d'ingénierie : ce sont des
 * conséquences directes de `strict_ndp`, calculées par l'API. Ils sont
 * déclarés ici parce qu'ils n'appartiennent pas au contrat du moteur.
 */
export type ReponseCalcul = Ec2BeamFlexureResponse & {
  signable: boolean;
  mention?: string;
  avertissement?: string;
};

/** Un refus. Ce n'est jamais un résultat partiel. */
export type Refus = { statut: number; erreur: EngineErrorDTO };

export type Issue =
  | { type: "resultat"; valeur: ReponseCalcul }
  | { type: "refus"; valeur: Refus }
  | { type: "panne"; message: string };

const BASE =
  process.env.NEXT_PUBLIC_EUROSTRUCT_API_URL ?? "http://127.0.0.1:8000";

/**
 * Lance la vérification en flexion.
 *
 * Rend une `Issue` explicite plutôt que de lever : un refus normatif n'est pas
 * une exception, c'est une réponse que l'ingénieur doit lire.
 */
export async function verifierFlexion(
  requete: Ec2BeamFlexureRequest,
): Promise<Issue> {
  let reponse: Response;
  try {
    reponse = await fetch(`${BASE}/v1/calculations/ec2/beam-flexure`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requete),
    });
  } catch (cause) {
    return {
      type: "panne",
      message:
        `l'API n'a pas repondu (${String(cause)}). Verifiez qu'elle tourne ` +
        `sur ${BASE} — voir eurostruct/api/README.md.`,
    };
  }

  const corps: unknown = await reponse.json().catch(() => null);
  if (reponse.ok) {
    return { type: "resultat", valeur: corps as ReponseCalcul };
  }
  if (corps && typeof corps === "object") {
    return {
      type: "refus",
      valeur: { statut: reponse.status, erreur: corps as EngineErrorDTO },
    };
  }
  return { type: "panne", message: `reponse ${reponse.status} illisible` };
}

/** URL de l'endpoint DXF. Le fichier est le corps de la réponse, pas un champ. */
export function urlDxf(): string {
  return `${BASE}/v1/calculations/ec2/beam-section.dxf`;
}

/**
 * Demande le DXF et déclenche son téléchargement.
 *
 * LE FERRAILLAGE EST SAISI, JAMAIS DEDUIT DU CALCUL. `As_required` dit
 * combien d'acier il faut ; il ne dit pas en combien de barres, de quel
 * diamètre, ni comment elles sont disposées. Choisir à la place de
 * l'ingénieur produirait un plan que personne n'a décidé.
 */
export async function telechargerDxf(
  requete: BeamSectionDrawingRequest,
): Promise<{ ok: true } | { ok: false; message: string }> {
  let reponse: Response;
  try {
    reponse = await fetch(urlDxf(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requete),
    });
  } catch (cause) {
    return { ok: false, message: `l'API n'a pas repondu (${String(cause)}).` };
  }
  if (!reponse.ok) {
    const corps: unknown = await reponse.json().catch(() => null);
    const detail =
      corps && typeof corps === "object" && "detail" in corps
        ? String((corps as { detail: unknown }).detail)
        : `reponse ${reponse.status}`;
    return { ok: false, message: detail };
  }

  const blob = await reponse.blob();
  const url = URL.createObjectURL(blob);
  const lien = document.createElement("a");
  lien.href = url;
  lien.download = `${requete.element || "section"}.dxf`;
  document.body.appendChild(lien);
  lien.click();
  lien.remove();
  // LIBERER L'URL. Sans cela le blob reste en memoire tant que l'onglet vit.
  URL.revokeObjectURL(url);
  return { ok: true };
}

/**
 * L'état du référentiel national d'un pays.
 *
 * `blocking` porte la même forme que les blocages d'un refus de calcul — c'est
 * le même préflight, appelé sans qu'aucune poutre n'ait été saisie.
 */
export type EtatReferentiel = {
  country_code: string;
  as_of: string;
  strict: boolean;
  ok: boolean;
  required: string[];
  blocking: BlockingParameterDTO[];
  referentiel: Record<string, number>;
  signable_possible: boolean;
  action: string;
};

/**
 * L'état du référentiel d'un pays. Aucune identité n'est requise : une
 * confirmation belge vaut pour toutes les études belges.
 *
 * Rend `null` si l'API ne répond pas. L'écran de calcul doit rester utilisable
 * sans ce bandeau : un bandeau absent apprend moins qu'une page blanche, mais
 * il n'empêche pas de travailler.
 */
export async function etatDuReferentiel(
  pays: string,
): Promise<EtatReferentiel | null> {
  try {
    const reponse = await fetch(`${BASE}/v1/ndp/${encodeURIComponent(pays)}`, {
      headers: { Accept: "application/json" },
    });
    if (!reponse.ok) return null;
    return (await reponse.json()) as EtatReferentiel;
  } catch {
    return null;
  }
}

export type { BeamSectionDrawingRequest, Ec2BeamFlexureRequest, EngineErrorDTO };
