/**
 * La vérification complète d'une poutre, vue du navigateur.
 *
 * CINQ CHAPITRES, UNE SEULE SAISIE, ET AUCUNE FORMULE ICI
 * --------------------------------------------------------
 * Flexion, effort tranchant, ancrage, ouverture des fissures, flèche : le
 * serveur les enchaîne dans cet ordre et rend cinq verdicts. Ce module ne
 * fait que poster et relire — il ne dérive rien, ne compose aucun taux, et
 * n'invente aucun statut.
 *
 * AUCUNE FORME N'EST REDÉFINIE
 * -----------------------------
 * `Ec2BeamVerificationRequest` et sa réponse viennent du contrat **généré**
 * depuis les modèles Pydantic. C'est ce qui interdit à l'écran d'envoyer un
 * champ que le serveur calcule : `status`, `may_be_finalised`, les empreintes,
 * `A_s`, le pays du projet n'existent pas dans le type de la requête, donc la
 * compilation les refuse avant que le serveur n'ait à le faire.
 *
 * LE RÉFÉRENTIEL NE PASSE PAS PAR ICI. Pays, région et date sont figés sur le
 * projet et lus côté serveur. L'URL nomme le projet ; le corps ne le nomme
 * pas non plus.
 */
import type {
  Ec2BeamVerificationRequest,
  Ec2BeamVerificationResponse,
  SectionOutcomeDTO,
} from "@contracts/generated/engine";
import { appelProtege, type PorteurDeJeton } from "@/lib/transport";

export type {
  Ec2BeamVerificationRequest,
  Ec2BeamVerificationResponse,
  SectionOutcomeDTO,
};

/**
 * L'ordre des cinq chapitres, tel que le moteur les exécute.
 *
 * IL EST FIXE, ET CE N'EST PAS UN DÉTAIL DE PRÉSENTATION. La flèche dépend de
 * la flexion ; l'afficher avant elle laisserait croire à deux verdicts
 * indépendants. Le serveur rend déjà les sections dans cet ordre : la liste
 * sert à les nommer à l'écran, jamais à les réordonner.
 */
export const CHAPITRES = [
  "flexure", "shear", "anchorage", "serviceability", "deflection",
] as const;

/**
 * Les quatre états d'un chapitre, en clair.
 *
 * `additional_analysis_required` N'EST PAS UN ÉCHEC, et `not_evaluated` N'EST
 * PAS UNE RÉUSSITE. Les confondre est exactement ce qui ferait signer une
 * étude dont un chapitre n'a jamais tourné.
 */
export const ETAT_LISIBLE: Record<string, string> = {
  passed: "Vérifié",
  failed: "Non vérifié",
  additional_analysis_required: "Analyse complémentaire due",
  not_evaluated: "Non évalué",
};

/** La classe CSS d'un état. Quatre états, quatre couleurs, aucune fusion. */
export const ETAT_CLASSE: Record<string, string> = {
  passed: "ok",
  failed: "ko",
  additional_analysis_required: "attente",
  not_evaluated: "silence",
};

/**
 * Poste une vérification complète **sur un projet**.
 *
 * ELLE PEUT ÊTRE REFUSÉE AVANT TOUT CALCUL, et c'est le comportement voulu :
 * en mode strict, un paramètre national non confirmé bloque au préflight, rien
 * n'est enregistré, et le 422 porte la liste des paramètres manquants. Ce
 * refus remonte tel quel — `AppelRefuse` — sans être transformé en résultat.
 *
 * PAS `idempotent`. Un POST rejoué après un 401 écrirait une seconde étude.
 */
export async function verifierPoutre(
  porteur: PorteurDeJeton,
  projectId: string,
  requete: Ec2BeamVerificationRequest,
): Promise<Ec2BeamVerificationResponse> {
  const etude = await appelProtege<Ec2BeamVerificationResponse>(
    `/v1/projects/${encodeURIComponent(projectId)}/beam-verifications`,
    porteur, { methode: "POST", corps: requete },
  );
  if (!etude?.calculation_id) {
    throw new Error("la verification n'a rendu aucun identifiant.");
  }
  return etude;
}

/**
 * Relit une étude enregistrée. RIEN N'EST RECALCULÉ.
 *
 * Le serveur rend ce qui a été écrit — les cinq verdicts, les empreintes,
 * l'instantané normatif. Relancer le moteur donnerait les nombres
 * d'aujourd'hui sous la date d'hier, et personne ne verrait la différence.
 */
export async function relireVerification(
  porteur: PorteurDeJeton,
  projectId: string,
  calculationId: string,
): Promise<Ec2BeamVerificationResponse> {
  const relue = await appelProtege<Ec2BeamVerificationResponse>(
    `/v1/projects/${encodeURIComponent(projectId)}/beam-verifications/`
    + encodeURIComponent(calculationId),
    porteur, { methode: "GET", idempotent: true },
  );
  if (!relue?.calculation_id) {
    throw new Error("l'etude relue n'a rendu aucun identifiant.");
  }
  return relue;
}

/**
 * Pourquoi une étude ne peut pas être finalisée, en une phrase — ou `null`.
 *
 * L'ÉCRAN N'EN DÉCIDE PAS, IL LE LIT. `may_be_finalised` est calculé par le
 * moteur et rendu par le serveur ; cette fonction ne fait que traduire la
 * raison en français, à partir des drapeaux que la réponse porte déjà.
 *
 * L'ORDRE DES CAUSES VA DE LA PLUS FERMANTE À LA PLUS FINE. Une étude
 * exploratoire ne sera jamais finalisable quoi qu'il arrive ensuite : le dire
 * en premier évite de laisser croire qu'il suffirait de corriger un chapitre.
 */
export function raisonDeNonFinalisation(
  etude: Ec2BeamVerificationResponse,
): string | null {
  if (etude.may_be_finalised) return null;
  if (etude.is_exploratory || !etude.strict_ndp) {
    return "Cette etude est exploratoire : elle a tourne avec des parametres "
      + "nationaux non confirmes. Aucune correction de section ne la rendra "
      + "finalisable — il faut la relancer en mode strict, apres confirmation "
      + "des parametres.";
  }
  if (!etude.preflight_ready) {
    return "Le referentiel national n'est pas complet pour cette etude : des "
      + "parametres restent a confirmer avant qu'un resultat puisse etre "
      + "oppose.";
  }
  if (etude.requires_additional_analysis) {
    return "Un chapitre demande une analyse complementaire. Elle n'est pas un "
      + "echec, mais elle n'est pas non plus une verification : tant qu'elle "
      + "n'est pas produite, l'etude ne conclut pas.";
  }
  const muets = (etude.sections ?? []).filter(
    (s) => s.status !== "passed").map((s) => s.title);
  if (muets.length) {
    return `Chapitre(s) sans verdict favorable : ${muets.join(", ")}.`;
  }
  return "Le serveur ne declare pas cette etude finalisable.";
}
