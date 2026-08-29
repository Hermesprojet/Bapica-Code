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

/** URL de téléchargement du DXF. Le fichier est le corps, pas un champ. */
export function urlDxf(): string {
  return `${BASE}/v1/calculations/ec2/beam-section.dxf`;
}

export type { Ec2BeamFlexureRequest, EngineErrorDTO };
