"use client";

/**
 * La verticale complète : saisir, vérifier, lire, produire.
 *
 * CE COMPOSANT NE FAIT QUE RELIER. Il détient la session, appelle le serveur,
 * et passe ce qui revient à `EtudeGuidee` et `SyntheseEtude`. Il ne compose
 * aucun verdict, ne dérive aucune valeur, et ne devine aucun statut.
 *
 * LE REFUS EST UN RÉSULTAT, PAS UNE PANNE
 * -----------------------------------------
 * En mode strict, un paramètre national non confirmé fait échouer le préflight
 * AVANT le calcul : le serveur rend 422, n'écrit rien, et joint la liste des
 * paramètres à faire relever dans l'Annexe Nationale publiée, chacun avec sa
 * clause et son module. C'est une liste de travail, et l'écran l'affiche comme
 * telle — pas comme une erreur technique.
 *
 * POURQUOI LES ACTIONS DISENT POURQUOI ELLES SONT IMPOSSIBLES
 * ------------------------------------------------------------
 * Une étude dont un chapitre échoue ne produit ni note ni plan : le serveur
 * refuse, et il a raison — un document se lit comme une conclusion. Mais un
 * bouton grisé sans motif envoie chercher la cause ailleurs, et la cause la
 * plus fréquente — l'étude exploratoire — ne se corrige pas en modifiant la
 * section. Chaque action porte donc son empêchement, écrit.
 */
import { useState } from "react";
//: LA FORME EXACTE QUE LA ROUTE REND, PAS SA VOISINE.
//:
//: `BlockingParameterDTO` nomme une cle du registre; `PreflightBlockerDTO`
//: nomme le PARAMETRE et le MODULE qui le reclame — un meme `gamma_C` sert
//: quatre modules sur cinq. Mesure du 01/09, au navigateur: l'ecran lisait
//: `key` et `standard` sur ces objets-la, et les onze parametres bloquants
//: s'affichaient sans nom. Un refus qui porte une liste de travail devenait
//: illisible.
import type { PreflightBlockerDTO } from "@contracts/generated/engine";
import { EtudeGuidee } from "./EtudeGuidee";
import { SyntheseEtude } from "./SyntheseEtude";
import {
  creerLivrable, previsualiserDessin, telechargerLivrable,
  type Projet,
} from "@/lib/atelier";
import {
  verifierPoutre,
  type Ec2BeamVerificationRequest, type Ec2BeamVerificationResponse,
} from "@/lib/verification";
import { AppelRefuse, SessionExpiree, type PorteurDeJeton } from "@/lib/transport";

/** Les rôles qui peuvent écrire sur un dossier. La frontière reste en base. */
const REDACTEURS = ["owner", "admin", "engineer"];

/** Les cinq chapitres, du nom que le moteur leur donne au nom qu'on lit. */
const MODULE_LISIBLE: Record<string, string> = {
  flexure: "flexion",
  shear: "effort tranchant",
  anchorage: "ancrage",
  serviceability: "ouverture des fissures",
  deflection: "flèche",
};

/** Ce que la dernière tentative a produit. Jamais un mélange des deux. */
type Etat =
  | { type: "vide" }
  | { type: "etude"; etude: Ec2BeamVerificationResponse }
  | { type: "refus"; message: string; bloquants: PreflightBlockerDTO[] }
  | { type: "panne"; message: string };

export function VerificationComplete({ projet, porteur, surEnregistrement }: {
  projet: Projet | null;
  porteur: PorteurDeJeton;
  //: L'historique et la liste des livrables partagent un compteur avec le
  //: reste de l'écran: une étude enregistrée qui n'apparaîtrait pas dans la
  //: liste juste au-dessus donnerait à croire qu'elle n'a rien écrit.
  surEnregistrement: () => void;
}) {
  const [etat, setEtat] = useState<Etat>({ type: "vide" });
  const [enCours, setEnCours] = useState(false);

  async function lancer(requete: Ec2BeamVerificationRequest) {
    if (!projet) return;
    setEnCours(true);
    setEtat({ type: "vide" });
    try {
      const etude = await verifierPoutre(porteur, projet.project_id, requete);
      setEtat({ type: "etude", etude });
    } catch (cause) {
      setEtat(enEtatDeRefus(cause));
    } finally {
      //: DANS TOUS LES CAS. Un refus de préflight n'écrit rien, mais un refus
      //: du moteur, si: la ligne existe et figure dans l'historique.
      surEnregistrement();
      setEnCours(false);
    }
  }

  //: LE DROIT D'ECRIRE SE LIT SUR L'ADHESION, ET L'ECRAN NE DECIDE DE RIEN.
  //: `member_role` est derive de l'adhesion cote serveur, et PostgreSQL reste
  //: la frontiere: ce motif sert a EXPLIQUER un bouton ferme, jamais a ouvrir
  //: quoi que ce soit. Un lecteur qui cliquerait quand meme recevrait le meme
  //: refus, en moins clair.
  const droit = !projet || (projet.member_active !== false
    && REDACTEURS.includes(projet.member_role))
    ? null
    : `Votre rôle sur ce dossier (« ${projet.member_role} »`
      + `${projet.member_active === false ? " , accès révoqué" : ""}) ne permet `
      + "pas d'y enregistrer une étude. La lecture reste ouverte.";

  return (
    <>
      <EtudeGuidee projet={projet} enCours={enCours} surLancer={lancer}
                   motifImpossible={droit} />

      {etat.type === "panne" && (
        <div className="bandeau refus" role="alert">
          <strong>L&apos;API n&apos;a pas répondu</strong>
          {etat.message}
        </div>
      )}

      {etat.type === "refus" && (
        <div className="bandeau refus" id="refus-verification" role="alert">
          <strong>Vérification refusée — rien n&apos;a été enregistré</strong>
          {etat.message}
          {etat.bloquants.length > 0 && (
            <>
              <p className="aide">
                Ces paramètres doivent être relevés dans l&apos;Annexe
                Nationale publiée, puis confirmés à quatre yeux. EUROSTRUCT ne
                les devine pas et n&apos;en propose aucune valeur.
              </p>
              <ul className="bloquants">
                {etat.bloquants.map((b, i) => (
                  <li key={`${b.module}-${b.parameter}-${i}`}>
                    <code>{b.parameter}</code> — {b.detail}
                    <span className="clause">
                      {`${b.clause} — ${b.annex}`}
                      {/* QUI LE RECLAME. Un meme parametre sert plusieurs
                          chapitres: sans le module, l'ingenieur ne sait pas
                          ce qu'il debloque en le faisant confirmer. */}
                      {` — reclame par : ${MODULE_LISIBLE[b.module] ?? b.module}`}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      {etat.type === "etude" && projet && (
        <SyntheseEtude
          etude={etat.etude}
          actions={<ActionsEtude projet={projet} porteur={porteur}
                                 etude={etat.etude}
                                 surLivrable={surEnregistrement} />} />
      )}
    </>
  );
}

/**
 * Ce qu'on peut tirer d'une étude, et pourquoi parfois rien.
 *
 * LES TROIS ACTIONS PARTENT DE L'ÉTUDE ENREGISTRÉE, jamais des champs saisis.
 * Le navigateur n'envoie ni section, ni barres, ni cadres : la coupe est gelée
 * avec l'étude, et le serveur la relit. C'est ce qui interdit qu'un plan
 * décrive une poutre qui n'a pas été vérifiée.
 */
function ActionsEtude({ projet, porteur, etude, surLivrable }: {
  projet: Projet; porteur: PorteurDeJeton;
  etude: Ec2BeamVerificationResponse; surLivrable: () => void;
}) {
  const [travail, setTravail] = useState<string | null>(null);
  const [apercu, setApercu] = useState<string | null>(null);
  const [echec, setEchec] = useState<string | null>(null);

  /**
   * L'EMPÊCHEMENT EST LE MÊME POUR LES TROIS, ET IL VIENT DU SERVEUR.
   * `project_calculation_is_publishable` refuse tout document tiré d'un calcul
   * qui ne conclut pas. L'écran le dit d'avance plutôt que de laisser
   * découvrir un 422 après un clic.
   */
  const empechement = etude.status === "passed" ? null
    : "Un chapitre au moins ne conclut pas. Une note ou un plan se lirait "
      + "comme une conclusion, et il n'y en a pas : corrigez la section, ou "
      + "produisez l'analyse complémentaire demandée, puis relancez l'étude.";

  async function agir(quoi: string, faire: () => Promise<void>) {
    setTravail(quoi);
    setEchec(null);
    try {
      await faire();
    } catch (cause) {
      setEchec(enPhrase(cause));
    } finally {
      setTravail(null);
    }
  }

  const produire = (format: "html" | "pdf" | "dxf", libelle: string) => () =>
    agir(libelle, async () => {
      const cree = await creerLivrable(porteur, projet.project_id, {
        calculation_id: etude.calculation_id, format,
      });
      await telechargerLivrable(porteur, projet.project_id,
                                cree.deliverable_id);
      surLivrable();
    });

  const voir = () => agir("apercu", async () => {
    //: `format: "dxf"` nomme le DOCUMENT visé — le plan de ferraillage — pas
    //: le codage de l'image: un navigateur ne lit pas le DXF, l'aperçu est
    //: donc du SVG. Il sort du MÊME modèle gelé que le fichier.
    setApercu(await previsualiserDessin(porteur, projet.project_id, {
      calculation_id: etude.calculation_id, format: "dxf",
    }));
  });

  return (
    <div className="actions-etude">
      <h3>Documents</h3>
      <div className="rangee-boutons">
        <button type="button" id="etude-note-html"
                disabled={!!empechement || !!travail}
                title={empechement ?? "Note de calcul à cinq chapitres, HTML"}
                onClick={produire("html", "note-html")}>
          {travail === "note-html" ? "Composition…" : "Note de calcul (HTML)"}
        </button>
        <button type="button" id="etude-note-pdf"
                disabled={!!empechement || !!travail}
                title={empechement ?? "Note de calcul à cinq chapitres, PDF"}
                onClick={produire("pdf", "note-pdf")}>
          {travail === "note-pdf" ? "Composition…" : "Note de calcul (PDF)"}
        </button>
        <button type="button" id="etude-plan-dxf"
                disabled={!!empechement || !!travail}
                title={empechement
                  ?? "Plan de ferraillage DXF R2018, depuis la coupe gelée"}
                onClick={produire("dxf", "plan")}>
          {travail === "plan" ? "Transcription…" : "Plan de ferraillage (DXF)"}
        </button>
        <button type="button" className="secondaire" id="etude-apercu"
                disabled={!!empechement || !!travail} onClick={voir}
                title={empechement ?? "Aperçu non contractuel, sans dépôt"}>
          {travail === "apercu" ? "Rendu…" : "Aperçu du plan"}
        </button>
      </div>

      {/* LE MOTIF EST ÉCRIT, PAS SEULEMENT SURVOLÉ. */}
      {empechement && (
        <p className="aide manque" id="pourquoi-pas-de-document" role="status">
          {empechement}
        </p>
      )}
      {!empechement && (
        <p className="aide">
          Le plan reprend la coupe gelée avec l&apos;étude — mêmes barres,
          mêmes cadres, même enrobage. Rien n&apos;est ressaisi, et rien
          n&apos;est recalculé.
        </p>
      )}
      {echec && <p className="bandeau refus" role="alert">{echec}</p>}

      {apercu && (
        <div className="apercu-plan" id="apercu-du-plan"
             /* Le SVG vient du serveur, composé par le moteur de dessin: il
                n'est jamais assemblé à partir d'une saisie du navigateur. */
             dangerouslySetInnerHTML={{ __html: apercu }} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// LA TRADUCTION DES REFUS. Un 422 du serveur porte un motif nommé; l'écran ne
// le remplace pas par une phrase à lui.
// ---------------------------------------------------------------------------
function enEtatDeRefus(cause: unknown): Etat {
  if (cause instanceof SessionExpiree) {
    return { type: "panne", message: "Session expirée : reconnectez-vous." };
  }
  if (cause instanceof AppelRefuse) {
    return {
      type: "refus",
      //: `AppelRefuse.detail` déplie déjà l'enveloppe `{detail: {...}}` de
      //: FastAPI. Le refaire ici donnerait une seconde lecture du même corps.
      message: cause.detail,
      bloquants: bloquantsDe(cause),
    };
  }
  return { type: "panne", message: enPhrase(cause) };
}

/**
 * Les paramètres bloquants joints au refus de préflight, s'il y en a.
 *
 * LA CLÉ EST `blocking`, celle que la route rend. La chercher ailleurs
 * afficherait une liste vide sur un refus qui en porte une — et l'ingénieur
 * conclurait qu'il n'y a rien à faire.
 */
function bloquantsDe(cause: AppelRefuse): PreflightBlockerDTO[] {
  const c = cause.corps;
  const noyau = (c && typeof c === "object" && "detail" in c)
    ? (c as { detail: unknown }).detail : c;
  if (!noyau || typeof noyau !== "object") return [];
  const liste = (noyau as { blocking?: unknown }).blocking;
  return Array.isArray(liste) ? liste as PreflightBlockerDTO[] : [];
}

function enPhrase(cause: unknown): string {
  if (cause instanceof AppelRefuse) return cause.detail;
  return cause instanceof Error ? cause.message : String(cause);
}
