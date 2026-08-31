"use client";

/**
 * L'écran de vérification en flexion.
 *
 * CE QUE CET ÉCRAN DOIT RENDRE LISIBLE, ET QUI N'EST PAS ÉVIDENT
 * ---------------------------------------------------------------
 * En mode strict — le défaut — le moteur REFUSE aujourd'hui pour tous les
 * pays, parce qu'aucun paramètre national n'est au statut `confirmed`.
 *
 * Ce refus n'est pas une panne, et il ne doit surtout pas ressembler à une
 * erreur technique : c'est une liste de travail. L'ingénieur reçoit les huit
 * paramètres à faire relever dans l'Annexe Nationale publiée, chacun avec sa
 * clause et sa référence. On l'affiche donc comme une liste actionnable.
 *
 * L'ÉCRAN NE CALCULE RIEN. Pas une formule, pas un arrondi. Il montre ce que
 * le moteur a décidé, et le refuse tel quel quand le moteur refuse.
 */
import { useEffect, useState } from "react";
import type { BlockingParameterDTO } from "@contracts/generated/engine";
import {
  etatDuReferentiel, planDeCharge, telechargerDxf, verifierFlexion,
  type Ec2BeamFlexureRequest, type Ec2BeamSectionRequest,
  type EtatReferentiel, type Issue, type ParametreNdp, type Pays,
  type PlanDeCharge, type ReponseCalcul,
} from "@/lib/api";
import {
  attesterLivrable, calculerEtEnregistrer, creerLivrable, creerProjet,
  emettreLivrable, historiqueDuProjet, listerLivrables, listerProjets,
  relireLivrable, renvoyerAuBrouillon, reviserLivrable, rouvrirCalcul,
  soumettreALaRelecture, telechargerDossierDeRevue,
  telechargerLivrable, telechargerNote,
  type CalculDeProjetRequest, type CalculEnregistre, type Livrable,
  type LivrableDetail, type Projet,
} from "@/lib/atelier";
import type { CalculResume } from "@contracts/generated/engine";
import {
  accepterInvitation,
  emettreInvitation,
  fonderOrganisation,
  listerInvitations,
  listerMembres,
  listerOrganisations,
  modifierMembre,
  peutAdministrer,
  revoquerInvitation,
  ROLE_EXPLIQUE,
  ROLES,
  type Invitation,
  type InvitationEmise,
  type Membre,
  type MembreModification,
  type Organisation,
} from "@/lib/organisation";
import { FournisseurAuth, useAuth } from "@/lib/authentification";
import { apiUrlConfiguree, DIAGNOSTIC_API_ABSENTE } from "@/lib/configuration";
import {
  approuverDecision, composerDossier, consommerDecision, proposerDecision,
  relireDecision,
  type AuthorityDecisionRequest, type AuthorityDecisionReview,
  type AuthorityReviewDossier,
} from "@/lib/autorite";
import { AppelRefuse, SessionExpiree } from "@/lib/transport";

type Champs = {
  b: string; h: string; d: string; M_Ed: string;
  beton: string; acier: string; element: string;
  //: LE TYPE DU CONTRAT, PAS `string`. C'est le seul écart qui obligeait à
  //: écrire `as never` sur la requête — un cast qui éteignait précisément le
  //: contrôle que le contrat généré existe pour exercer.
  pays: Pays;
  strict: boolean;
};

const DEFAUTS: Champs = {
  b: "300", h: "500", d: "450", M_Ed: "150",
  beton: "C25/30", acier: "B500B", pays: "BE", element: "P1",
  strict: true,
};

/**
 * LA SESSION EST DÉTENUE ICI, AU-DESSUS DE TOUT LE RESTE.
 *
 * Elle vivait dans l'état local de `Connexion` : le jeton était obtenu,
 * affiché, et **jamais utilisé** — aucun autre composant ne pouvait le voir.
 * Le fournisseur la remonte, si bien que les décisions d'autorité s'en
 * servent, que l'expiration se surveille en un seul endroit, et que la
 * déconnexion vide la seule copie qui existe.
 */
export default function Page() {
  return (
    <FournisseurAuth>
      <Ecran />
    </FournisseurAuth>
  );
}

function Ecran() {
  const auth = useAuth();
  //: LE PROJET SÉLECTIONNÉ, ET LA DIFFÉRENCE QU'IL FAIT.
  //:
  //: Sans projet, le calcul reste EXPLORATOIRE: il passe par la route
  //: publique, ne touche aucune base, et disparaît au rechargement. C'est
  //: exactement ce qu'était le produit entier jusqu'ici, avec
  //: `project_id: "DEMO-001"` écrit en dur.
  //:
  //: Avec un projet, il passe par la route de l'atelier, qui l'enregistre —
  //: requête exacte, journal, résultats et vérifications — en une seule
  //: transaction, puis le rend relu depuis la base.
  const [projet, setProjet] = useState<Projet | null>(null);
  //: Ce que l'historique incrémente pour se redemander. Un calcul enregistré
  //: qui n'apparaîtrait pas dans la liste juste au-dessus donnerait à croire
  //: qu'il n'a pas été sauvegardé.
  const [revisionAtelier, setRevisionAtelier] = useState(0);
  const [champs, setChamps] = useState<Champs>(DEFAUTS);
  const [issue, setIssue] = useState<Issue | null>(null);
  const [enCours, setEnCours] = useState(false);
  //: L'ETAT DU REFERENTIEL EST DATE, ET LA CONSOMMATION LE PERIME.
  //:
  //: Le bandeau annonce « 0 / 29 ». Apres une decision consommee c'est faux,
  //: et l'ecran continuait de l'afficher: le seul effet visible du parcours
  //: d'autorite restait donc invisible. Ce compteur est ce que la
  //: consommation incremente pour que le bandeau redemande.
  const [revision, setRevision] = useState(0);

  //: LE REFERENTIEL EFFECTIF. Avec un projet, il vient du projet — et de lui
  //: seul. Le selecteur de pays du formulaire ne decide plus rien: il est
  //: verrouille, et sa valeur affichee est celle du dossier.
  //:
  //: LES DEUX BANDEAUX LE SUIVENT. Le plan de charge NDP et les decisions
  //: d'autorite portaient sur `champs.pays`: un ingenieur travaillant sur un
  //: projet belge pouvait confirmer des parametres francais depuis le meme
  //: ecran, et lire l'etat d'un referentiel qui n'etait pas le sien.
  const paysEffectif: Pays = projet ? (projet.country as Pays) : champs.pays;

  const majuscule = (k: keyof Champs) => (e: { target: { value: string } }) =>
    setChamps((c) => ({ ...c, [k]: e.target.value }));

  // Le sélecteur ne peut rendre que les quatre pays du contrat: on le dit au
  // typage plutôt que de le supposer.
  const changerPays = (e: { target: { value: string } }) =>
    setChamps((c) => ({ ...c, pays: e.target.value as Pays }));

  /** La matière du calcul : géométrie, matériaux, moment. Aucun référentiel. */
  function matiere() {
    return {
      element: champs.element,
      strict_ndp: champs.strict,
      M_Ed: { value: Number(champs.M_Ed), unit: "kN*m" },
      section: {
        b: { value: Number(champs.b), unit: "mm" },
        h: { value: Number(champs.h), unit: "mm" },
        d: { value: Number(champs.d), unit: "mm" },
      },
      materials: { concrete_grade: champs.beton, steel_grade: champs.acier },
    };
  }

  /**
   * La requête EXPLORATOIRE. Elle nomme son référentiel, parce qu'aucun projet
   * ne le fixe : c'est une aide au dimensionnement, et rien n'en est écrit.
   *
   * `project_id` y est un repère de note — nommé « exploratoire », plutôt que
   * `DEMO-001` qui ressemblait à un identifiant et n'en était pas un.
   */
  function requeteExploratoire(): Ec2BeamFlexureRequest {
    return { project_id: "exploratoire", country: champs.pays, ...matiere() };
  }

  /**
   * Le corps du calcul DE PROJET. Il ne peut pas nommer un référentiel.
   *
   * Le type généré ne porte ni `project_id`, ni `country`, ni `region`, ni
   * `as_of` : les quatre viennent du projet, lus côté serveur. Mesuré avant ce
   * verrou : un corps annonçant `country=FR` et `as_of=2030-01-01` sur un
   * projet belge daté de 2024 obtenait un 201, et la ligne enregistrée se
   * contredisait.
   */
  function corpsDeProjet(): CalculDeProjetRequest {
    return matiere();
  }

  /** Calcul EXPLORATOIRE. Rien n'est écrit, et l'écran le dit. */
  async function soumettre(e: React.FormEvent) {
    e.preventDefault();
    setEnCours(true);
    setIssue(null);
    setIssue(await verifierFlexion(requeteExploratoire()));
    setEnCours(false);
  }

  /**
   * Calcul ENREGISTRÉ, sur le projet sélectionné.
   *
   * LE REFUS EST AFFICHÉ COMME UN REFUS, et il a quand même été enregistré:
   * le serveur écrit la ligne avant de rendre le 422. L'écran n'a donc rien à
   * faire de particulier — sinon rafraîchir l'historique, où le refus figure.
   */
  async function enregistrer() {
    if (!projet) return;
    setEnCours(true);
    setIssue(null);
    try {
      const calcul = await calculerEtEnregistrer(
        auth.porteur, projet.project_id, corpsDeProjet());
      setIssue(issueDepuisEnregistre(calcul));
    } catch (cause) {
      setIssue(issueDepuisErreur(cause));
    } finally {
      // DANS TOUS LES CAS. Un refus est une ligne d'historique comme une
      // autre, et ne pas rafraîchir donnerait à croire qu'il n'a rien laissé.
      setRevisionAtelier((n) => n + 1);
      setEnCours(false);
    }
  }

  return (
    <main>
      <h1>EUROSTRUCT — flexion simple, section rectangulaire</h1>
      <p className="sous-titre">
        Vérification ELU selon EN 1992-1-1 et son Annexe Nationale.
      </p>

      <ConfigurationManquante />
      <Connexion />
      {/* LE BUREAU AVANT L'ATELIER, ET C'EST L'ORDRE DU PARCOURS REEL: on
          appartient a une organisation AVANT d'avoir un projet. Un compte tout
          neuf voyait jusqu'ici un selecteur de projets vide, sans un mot sur ce
          qui manquait. */}
      <Bureau surChangement={() => setRevisionAtelier((n) => n + 1)} />
      <Atelier projet={projet} surSelection={setProjet}
               revision={revisionAtelier} />
      <DecisionsAutorite pays={paysEffectif}
                         surConsommation={() => setRevision((n) => n + 1)} />
      <Referentiel pays={paysEffectif} revision={revision} />

      <form onSubmit={soumettre}>
        <fieldset>
          <legend>Section</legend>
          <div className="grille">
            <div>
              <label htmlFor="b">Largeur b (mm)</label>
              <input id="b" inputMode="decimal" value={champs.b}
                     onChange={majuscule("b")} />
            </div>
            <div>
              <label htmlFor="h">Hauteur h (mm)</label>
              <input id="h" inputMode="decimal" value={champs.h}
                     onChange={majuscule("h")} />
            </div>
            <div>
              <label htmlFor="d">Hauteur utile d (mm)</label>
              <input id="d" inputMode="decimal" value={champs.d}
                     onChange={majuscule("d")} />
            </div>
            <div>
              <label htmlFor="m">Moment M<sub>Ed</sub> (kN·m)</label>
              <input id="m" inputMode="decimal" value={champs.M_Ed}
                     onChange={majuscule("M_Ed")} />
            </div>
          </div>
        </fieldset>

        <fieldset>
          <legend>Matériaux et référentiel</legend>
          <div className="grille">
            <div>
              <label htmlFor="beton">Béton</label>
              <input id="beton" value={champs.beton} onChange={majuscule("beton")} />
            </div>
            <div>
              <label htmlFor="acier">Acier</label>
              <input id="acier" value={champs.acier} onChange={majuscule("acier")} />
            </div>
            <div>
              <label htmlFor="pays">Pays</label>
              {/* VERROUILLE SUR LE PROJET. Le pays, la région et la date de
                  référence désignent ensemble l'édition d'Annexe Nationale
                  applicable: ils se figent à la création du projet, et aucun
                  calcul du dossier ne peut en désigner d'autres. Le champ
                  reste VISIBLE — masquer le référentiel appliqué serait pire
                  que de le montrer inerte. */}
              <select id="pays" value={paysEffectif} onChange={changerPays}
                      disabled={!!projet}
                      title={projet
                        ? "Figé sur le projet: le référentiel d'un dossier ne "
                          + "change pas d'un calcul à l'autre."
                        : undefined}>
                <option value="BE">Belgique</option>
                <option value="FR">France</option>
                <option value="ES">Espagne</option>
                <option value="DE">Allemagne</option>
              </select>
            </div>
            {projet && (
              <div>
                <label htmlFor="ctx">Référentiel du projet</label>
                <input id="ctx" readOnly value={
                  `${projet.country}`
                  + `${projet.region ? " — " + projet.region : ""}`
                  + ` — ${projet.ndp_as_of}`} />
                <span className="aide">
                  Figé à la création. Il résout l&apos;édition
                  d&apos;Annexe Nationale en vigueur.
                </span>
              </div>
            )}
            <div>
              <label htmlFor="element">Repère</label>
              <input id="element" value={champs.element}
                     onChange={majuscule("element")} />
            </div>
          </div>

          <div className="ligne-case">
            <input id="strict" type="checkbox" checked={champs.strict}
                   onChange={(e) =>
                     setChamps((c) => ({ ...c, strict: e.target.checked }))} />
            <label htmlFor="strict">
              Mode strict (paramètres nationaux confirmés exigés)
              <span className="aide">
                Décoché, le calcul utilise des valeurs non confirmées et le
                résultat porte la mention <strong>PROJET — NON SIGNABLE</strong>.
              </span>
            </label>
          </div>
        </fieldset>

        <button type="submit" disabled={enCours}>
          {enCours ? "Calcul en cours…" : "Vérifier (exploratoire)"}
        </button>

        {/* DEUX BOUTONS, ET LEUR DIFFÉRENCE EST ÉCRITE.
            « Vérifier » ne laisse aucune trace: c'est ce que faisait tout
            l'écran jusqu'ici. « Calculer et enregistrer » écrit le calcul sur
            le projet — requête exacte, journal, résultats et vérifications —
            et il survit au rechargement. Confondre les deux ferait croire à un
            enregistrement qui n'a pas lieu. */}
        <button type="button" disabled={enCours || !projet}
                onClick={enregistrer}
                title={projet ? `Enregistrer sur « ${projet.name} »`
                              : "Sélectionner un projet d'abord"}>
          {enCours ? "En cours…" : "Calculer et enregistrer sur le projet"}
        </button>
        {!projet && (
          <p className="aide">
            Aucun projet sélectionné : le calcul reste exploratoire et
            disparaîtra au rechargement.
          </p>
        )}
      </form>

      {projet && (
        <Historique projet={projet} revision={revisionAtelier}
                    surReouverture={setIssue}
                    surLivrable={() => setRevisionAtelier((n) => n + 1)} />
      )}

      {/* LES LIVRABLES SUIVENT L'HISTORIQUE, ET PARTAGENT SON COMPTEUR.
          Produire un brouillon depuis l'historique doit le faire apparaitre
          ici sans rechargement: deux compteurs separes laisseraient l'une des
          deux listes en retard sur l'autre, et c'est toujours celle qu'on
          regarde. */}
      {projet && (
        <Livrables projet={projet} revision={revisionAtelier}
                   surChangement={() => setRevisionAtelier((n) => n + 1)} />
      )}

      {issue?.type === "panne" && (
        <div className="bandeau refus" role="alert">
          <strong>L&apos;API n&apos;a pas répondu</strong>
          {issue.message}
        </div>
      )}

      {issue?.type === "refus" && <Refus issue={issue} />}
      {issue?.type === "resultat" && <Resultat issue={issue} />}

      <p className="pied">
        Un résultat ne peut être soumis à un ingénieur que si les paramètres
        nationaux utilisés sont confirmés — et sa signature reste un acte
        humain, qu&apos;aucun calcul ne remplace.
      </p>
    </main>
  );
}

// ===========================================================================
// L'ATELIER — projets, historique, réouverture
// ===========================================================================

/**
 * Un calcul enregistré, projeté dans la forme que l'écran de résultat affiche.
 *
 * POURQUOI PROJETER PLUTÔT QU'ÉCRIRE UN SECOND ÉCRAN. `Resultat` sait déjà
 * afficher un calcul — les cartes, le journal, les vérifications, la mention.
 * En écrire un deuxième pour les calculs relus donnerait deux rendus du même
 * objet, et c'est toujours le moins entretenu qui finit par mentir sur un
 * taux d'utilisation.
 *
 * ON NE FABRIQUE AUCUNE VALEUR AU PASSAGE. Ce qui manque au calcul relu — il
 * n'en manque pas, la base porte le résultat entier — n'est pas comblé.
 */
function issueDepuisEnregistre(calcul: CalculEnregistre): Issue {
  //: `results.payload` PORTE LE DOCUMENT: le resultat, le rapport de
  //: verification avec la reference citable de chaque clause, et le repere.
  //: La table `verifications` en est l'index interrogeable, pas la source de
  //: l'affichage — la recomposer ici ferait dire a l'ecran autre chose que ce
  //: qui ira dans la note.
  const paquet = (calcul.result ?? {}) as Record<string, unknown>;
  return {
    type: "resultat",
    valeur: {
      element: paquet.element,
      result: paquet.result,
      verification: paquet.verification,
      engine_version: calcul.engine_version,
      journal: calcul.journal,
      // LES DEUX CONSÉQUENCES DU MODE STRICT, telles que la base les porte.
      // Les recalculer ici ferait dire à l'écran autre chose que ce qui est
      // enregistré.
      strict_ndp_satisfied: calcul.strict_ndp && calcul.status === "succeeded",
      eligible_for_engineering_review:
        calcul.strict_ndp && calcul.status === "succeeded",
      exploratory: !calcul.strict_ndp,
      notice: calcul.notice,
      mention: calcul.mention ?? undefined,
    } as unknown as ReponseCalcul,
    requete: calcul.request as unknown as Ec2BeamFlexureRequest,
  };
}

/** Une erreur de transport, dite comme telle et jamais comme un résultat. */
function issueDepuisErreur(cause: unknown): Issue {
  if (cause instanceof AppelRefuse) {
    return { type: "panne", message: `${cause.statut} — ${cause.message}` };
  }
  return { type: "panne", message: String(cause) };
}

/**
 * Les projets de l'organisation, leur création, et la sélection.
 *
 * IL NE S'AFFICHE PAS SANS SESSION, et il le dit. Un projet nomme un client et
 * une adresse : la liste n'existe pas pour un visiteur, et une liste vide
 * affichée à sa place se lirait « vous n'avez aucun projet ».
 *
 * AUCUNE ORGANISATION N'EST SAISIE ICI. Elle sort des appartenances en base.
 * Le seul cas où elle se poserait — un ingénieur de plusieurs bureaux — reçoit
 * aujourd'hui un refus nommé du serveur plutôt qu'un choix deviné, et le champ
 * viendra quand le cas se présentera vraiment.
 */
function Atelier({ projet, surSelection, revision = 0 }: {
  projet: Projet | null;
  surSelection: (p: Projet | null) => void;
  //: CE QUE LA FONDATION D'UN BUREAU INCREMENTE.
  //:
  //: Sans lui, l'atelier demandait ses projets UNE fois, a la connexion.
  //: Quelqu'un qui fondait son bureau juste apres restait devant un selecteur
  //: vide et le meme refus qu'avant — le produit avait fait ce qu'il fallait,
  //: et l'ecran disait le contraire.
  revision?: number;
}) {
  const auth = useAuth();
  const [projets, setProjets] = useState<Projet[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [ouvrirCreation, setOuvrirCreation] = useState(false);
  const [nom, setNom] = useState("");
  const [reference, setReference] = useState("");
  const [region, setRegion] = useState("");
  const [pays, setPays] = useState<Pays>("BE");
  const [dateRef, setDateRef] = useState(
    () => new Date().toISOString().slice(0, 10));
  const [enCours, setEnCours] = useState(false);

  useEffect(() => {
    if (!auth.connecte) {
      setProjets(null);
      surSelection(null);
      return;
    }
    let vivant = true;
    listerProjets(auth.porteur)
      .then((liste) => { if (vivant) { setProjets(liste); setErreur(null); } })
      .catch((cause) => {
        // UNE PANNE N'EST PAS UNE LISTE VIDE. Les confondre ferait afficher
        // « aucun projet » à quelqu'un qui en a douze.
        if (vivant) { setProjets(null); setErreur(String(cause)); }
      });
    return () => { vivant = false; };
  }, [auth.connecte, auth.porteur, surSelection, revision]);

  if (!auth.connecte) return null;

  async function creer(e: React.FormEvent) {
    e.preventDefault();
    setEnCours(true);
    setErreur(null);
    try {
      const cree = await creerProjet(auth.porteur, {
        name: nom, reference: reference || null, country: pays,
        // LA CHAINE VIDE N'EST PAS UNE REGION. `null` et `""` se compareraient
        // differemment au contexte du calcul, et la base refuserait alors des
        // calculs corrects.
        region: region.trim() || null,
        ndp_as_of: dateRef, organization_id: null,
      });
      setProjets((liste) => [cree, ...(liste ?? [])]);
      surSelection(cree);
      setOuvrirCreation(false);
      setNom("");
      setReference("");
      setRegion("");
    } catch (cause) {
      setErreur(String(cause));
    } finally {
      setEnCours(false);
    }
  }

  return (
    <section className="bandeau">
      <strong>Atelier</strong>
      {erreur && <p role="alert">{erreur}</p>}

      <div className="grille">
        <div>
          <label htmlFor="projet">Projet</label>
          <select id="projet" value={projet?.project_id ?? ""}
                  onChange={(e) => surSelection(
                    projets?.find((p) => p.project_id === e.target.value)
                    ?? null)}>
            <option value="">— aucun (calcul exploratoire) —</option>
            {(projets ?? []).map((p) => (
              <option key={p.project_id} value={p.project_id}>
                {p.name}{p.reference ? ` — ${p.reference}` : ""} ({p.country},
                {" "}{p.calculation_count} calcul
                {p.calculation_count === 1 ? "" : "s"})
              </option>
            ))}
          </select>
        </div>
        <div>
          <button type="button"
                  onClick={() => setOuvrirCreation((o) => !o)}>
            {ouvrirCreation ? "Annuler" : "Nouveau projet"}
          </button>
        </div>
      </div>

      {projet && (
        <p className="aide">
          {projet.organization_name} — {projet.country}
          {projet.region ? ` / ${projet.region}` : ""}, référentiel figé au
          {" "}{projet.ndp_as_of}.
        </p>
      )}

      {ouvrirCreation && (
        <form onSubmit={creer}>
          <div className="grille">
            <div>
              <label htmlFor="p-nom">Nom</label>
              <input id="p-nom" value={nom} required
                     onChange={(e) => setNom(e.target.value)} />
            </div>
            <div>
              <label htmlFor="p-ref">Référence</label>
              <input id="p-ref" value={reference}
                     onChange={(e) => setReference(e.target.value)} />
            </div>
            <div>
              <label htmlFor="p-pays">Pays</label>
              <select id="p-pays" value={pays}
                      onChange={(e) => setPays(e.target.value as Pays)}>
                <option value="BE">Belgique</option>
                <option value="FR">France</option>
                <option value="ES">Espagne</option>
                <option value="DE">Allemagne</option>
              </select>
            </div>
            <div>
              <label htmlFor="p-region">Région</label>
              <input id="p-region" value={region}
                     onChange={(e) => setRegion(e.target.value)} />
              <span className="aide">
                Facultative. Elle change les paramètres nationaux là où ils
                sont régionalisés (Wallonie, Land, Comunidad autónoma).
              </span>
            </div>
            <div>
              <label htmlFor="p-date">Date de référence</label>
              <input id="p-date" type="date" value={dateRef} required
                     onChange={(e) => setDateRef(e.target.value)} />
              <span className="aide">
                Elle résout l&apos;édition d&apos;Annexe Nationale en vigueur,
                et se fige à la création.
              </span>
            </div>
          </div>
          <button type="submit" disabled={enCours || !nom.trim()}>
            {enCours ? "Création…" : "Créer le projet"}
          </button>
        </form>
      )}
    </section>
  );
}


/**
 * LE BUREAU — LA PORTE D'ENTRÉE, ET L'ADMINISTRATION DE L'ÉQUIPE.
 *
 * CE QU'IL REMPLACE : RIEN. Il n'y avait rien. Un compte tout neuf,
 * parfaitement authentifié, arrivait devant une liste de projets vide — pas
 * une erreur, pas une explication, un écran nu — et aucun bouton ne permettait
 * d'en sortir. La seule façon d'exister dans l'application était un `insert`
 * fait à la main par le propriétaire de la base.
 *
 * DEUX ÉCRANS, ET LA DIFFÉRENCE COMPTE. « Zéro projet et zéro bureau » n'est
 * pas « zéro projet et un bureau » : le premier appelle « créez votre bureau »,
 * le second « créez votre premier projet ». Une seule liste vide ne permettait
 * pas de les distinguer, et c'est pour cela que les organisations se
 * demandent séparément des projets.
 *
 * AUCUN BOUTON DÉCORATIF. Le panneau d'administration n'apparaît que pour un
 * `owner` ou un `admin`, et pour les autres l'écran EXPLIQUE au lieu de
 * cacher. La frontière, elle, est dans PostgreSQL : `project_exiger_capacite`
 * refuse quel que soit l'appelant, et la route la rejoue.
 */
function Bureau({ surChangement }: { surChangement: () => void }) {
  const auth = useAuth();
  const [bureaux, setBureaux] = useState<Organisation[] | null>(null);
  const [choisi, setChoisi] = useState<string>("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);

  //: LE FORMULAIRE DE FONDATION.
  const [ouvrirFondation, setOuvrirFondation] = useState(false);
  const [nomBureau, setNomBureau] = useState("");
  const [paysBureau, setPaysBureau] = useState<Pays>("BE");
  const [monNom, setMonNom] = useState("");
  const [monOrdre, setMonOrdre] = useState("");

  //: LE FORMULAIRE D'ADHÉSION PAR LIEN.
  const [ouvrirAdhesion, setOuvrirAdhesion] = useState(false);
  const [lien, setLien] = useState("");

  const [enCours, setEnCours] = useState(false);

  useEffect(() => {
    if (!auth.connecte) { setBureaux(null); setChoisi(""); return; }
    let vivant = true;
    listerOrganisations(auth.porteur)
      .then((liste) => {
        if (!vivant) return;
        setBureaux(liste);
        setErreur(null);
        // ON NE CHOISIT PAS A LA PLACE DE QUELQU'UN QUI A PLUSIEURS BUREAUX:
        // on preselectionne seulement quand il n'y a pas d'ambiguite.
        setChoisi((actuel) => actuel
          || (liste.length === 1 ? liste[0].organization_id : ""));
      })
      .catch((cause) => {
        // UNE PANNE N'EST PAS UNE ABSENCE DE BUREAU. Les confondre ferait
        // proposer « créez votre organisation » à quelqu'un qui en a une, et
        // il en créerait une seconde.
        if (vivant) { setBureaux(null); setErreur(String(cause)); }
      });
    return () => { vivant = false; };
  }, [auth.connecte, auth.porteur, revision]);

  if (!auth.connecte) return null;

  const courant = (bureaux ?? []).find((o) => o.organization_id === choisi)
    ?? null;

  async function fonder(e: React.FormEvent) {
    e.preventDefault();
    setEnCours(true);
    setErreur(null);
    try {
      const cree = await fonderOrganisation(auth.porteur, {
        name: nomBureau, country: paysBureau,
        display_name: monNom.trim() || null,
        professional_id: monOrdre.trim() || null,
      });
      setChoisi(cree.organization_id);
      setOuvrirFondation(false);
      setNomBureau("");
      setRevision((n) => n + 1);
      surChangement();
    } catch (cause) {
      setErreur(String(cause));
    } finally {
      setEnCours(false);
    }
  }

  async function rejoindre(e: React.FormEvent) {
    e.preventDefault();
    setEnCours(true);
    setErreur(null);
    try {
      const entree = await accepterInvitation(auth.porteur, lien.trim());
      setChoisi(entree.organization_id);
      setOuvrirAdhesion(false);
      setLien("");
      setRevision((n) => n + 1);
      surChangement();
    } catch (cause) {
      setErreur(String(cause));
    } finally {
      setEnCours(false);
    }
  }

  return (
    <section className="bandeau" id="bureau">
      <strong>Bureau</strong>
      {erreur && <p role="alert">{erreur}</p>}

      {bureaux !== null && bureaux.length === 0 && (
        <div id="aucun-bureau">
          <p>
            Vous n&apos;appartenez à aucun bureau d&apos;études. Un projet
            appartient à une organisation&nbsp;: sans elle, rien ne peut être
            créé, et l&apos;écran resterait vide indéfiniment.
          </p>
          <div className="grille">
            <button type="button" id="creer-bureau"
                    onClick={() => { setOuvrirFondation((o) => !o);
                                     setOuvrirAdhesion(false); }}>
              {ouvrirFondation ? "Annuler" : "Créer mon organisation"}
            </button>
            <button type="button" id="rejoindre-bureau"
                    onClick={() => { setOuvrirAdhesion((o) => !o);
                                     setOuvrirFondation(false); }}>
              {ouvrirAdhesion ? "Annuler" : "Rejoindre avec une invitation"}
            </button>
          </div>
        </div>
      )}

      {bureaux !== null && bureaux.length > 0 && (
        <div className="grille">
          <div>
            <label htmlFor="bureau-choisi">Organisation</label>
            <select id="bureau-choisi" value={choisi}
                    onChange={(e) => setChoisi(e.target.value)}>
              <option value="">— choisir —</option>
              {bureaux.map((o) => (
                <option key={o.organization_id} value={o.organization_id}>
                  {o.name} ({o.country}) — {o.member_role}
                </option>
              ))}
            </select>
          </div>
          <div>
            <button type="button" id="rejoindre-bureau"
                    onClick={() => { setOuvrirAdhesion((o) => !o);
                                     setOuvrirFondation(false); }}>
              {ouvrirAdhesion ? "Annuler" : "Rejoindre avec une invitation"}
            </button>
          </div>
        </div>
      )}

      {ouvrirFondation && (
        <form onSubmit={fonder} id="formulaire-fondation">
          <fieldset>
            <legend>Créer mon organisation</legend>
            <div className="grille">
              <div>
                <label htmlFor="nom-bureau">Nom du bureau</label>
                <input id="nom-bureau" value={nomBureau}
                       onChange={(e) => setNomBureau(e.target.value)} />
              </div>
              <div>
                <label htmlFor="pays-bureau">Pays</label>
                <select id="pays-bureau" value={paysBureau}
                        onChange={(e) => setPaysBureau(e.target.value as Pays)}>
                  <option value="BE">Belgique</option>
                  <option value="FR">France</option>
                  <option value="ES">Espagne</option>
                  <option value="DE">Allemagne</option>
                </select>
              </div>
              <div>
                <label htmlFor="mon-nom">Votre nom professionnel</label>
                <input id="mon-nom" value={monNom}
                       onChange={(e) => setMonNom(e.target.value)} />
                <span className="aide">
                  Il figurera sur les attestations que vous signerez. Sans lui,
                  la base refuse d&apos;attester.
                </span>
              </div>
              <div>
                <label htmlFor="mon-ordre">
                  Numéro d&apos;inscription (facultatif)
                </label>
                <input id="mon-ordre" value={monOrdre}
                       onChange={(e) => setMonOrdre(e.target.value)} />
                <span className="aide">
                  Reproduit tel quel. Il n&apos;est vérifié par personne ici.
                </span>
              </div>
            </div>
            <button type="submit" id="valider-fondation"
                    disabled={enCours || !nomBureau.trim()}>
              {enCours ? "Création…" : "Créer le bureau"}
            </button>
          </fieldset>
        </form>
      )}

      {ouvrirAdhesion && (
        <form onSubmit={rejoindre} id="formulaire-adhesion">
          <fieldset>
            <legend>Rejoindre avec une invitation</legend>
            <div>
              <label htmlFor="lien-invitation">Lien reçu</label>
              <input id="lien-invitation" value={lien}
                     onChange={(e) => setLien(e.target.value)} />
              <span className="aide">
                Le lien est à usage unique et expire. Il ne dit pas de quel
                bureau il vient&nbsp;: c&apos;est en le présentant que vous
                l&apos;apprenez.
              </span>
            </div>
            <button type="submit" id="valider-adhesion"
                    disabled={enCours || !lien.trim()}>
              {enCours ? "Adhésion…" : "Rejoindre"}
            </button>
          </fieldset>
        </form>
      )}

      {courant && <Equipe organisation={courant} />}
    </section>
  );
}

/**
 * L'ÉQUIPE DU BUREAU — membres et invitations, pour qui l'administre.
 *
 * POUR LES AUTRES, L'ÉCRAN EXPLIQUE AU LIEU DE CACHER. Un panneau qui
 * disparaît sans un mot laisse chercher ce qu'on a mal fait ; un panneau qui
 * dit « votre rôle n'administre pas les membres » se comprend tout de suite.
 *
 * LE SECRET D'UNE INVITATION N'EST MONTRÉ QU'UNE FOIS, ici, juste après son
 * émission. Il n'existe nulle part ailleurs — ni en base, ni dans la liste
 * ci-dessous, ni après un rechargement. Le recharger ne le ramènera pas : il
 * faut révoquer et réémettre.
 */
function Equipe({ organisation }: { organisation: Organisation }) {
  const auth = useAuth();
  const [membres, setMembres] = useState<Membre[] | null>(null);
  const [invitations, setInvitations] = useState<Invitation[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [enCours, setEnCours] = useState(false);

  const [role, setRole] = useState<string>("engineer");
  const [libelle, setLibelle] = useState("");
  const [nomInvite, setNomInvite] = useState("");
  const [ordreInvite, setOrdreInvite] = useState("");
  //: LE LIEN TOUT JUSTE ÉMIS. Il vit dans l'état de ce composant, et nulle
  //: part ailleurs: ni `localStorage`, ni URL. Un secret rangé dans le
  //: navigateur survivrait à la session, ce qu'un lien à usage unique ne doit
  //: pas faire.
  const [lienEmis, setLienEmis] = useState<InvitationEmise | null>(null);

  const administre = peutAdministrer(organisation);

  useEffect(() => {
    if (!administre) { setMembres(null); setInvitations(null); return; }
    let vivant = true;
    Promise.all([
      listerMembres(auth.porteur, organisation.organization_id),
      listerInvitations(auth.porteur, organisation.organization_id),
    ])
      .then(([m, i]) => {
        if (!vivant) return;
        setMembres(m); setInvitations(i); setErreur(null);
      })
      .catch((cause) => {
        if (vivant) { setMembres(null); setInvitations(null);
                      setErreur(String(cause)); }
      });
    return () => { vivant = false; };
  }, [auth.porteur, organisation.organization_id, administre, revision]);

  if (!administre) {
    return (
      <p id="pourquoi-pas-admin" className="aide">
        Votre rôle dans ce bureau est «&nbsp;{organisation.member_role}
        &nbsp;»&nbsp;: il n&apos;administre pas les membres. Inviter quelqu&apos;un,
        changer un rôle ou révoquer un accès relève d&apos;un
        «&nbsp;owner&nbsp;» ou d&apos;un «&nbsp;admin&nbsp;».
      </p>
    );
  }

  async function inviter(e: React.FormEvent) {
    e.preventDefault();
    setEnCours(true);
    setErreur(null);
    setLienEmis(null);
    try {
      const emise = await emettreInvitation(
        auth.porteur, organisation.organization_id, {
          role, label: libelle.trim() || null,
          display_name: nomInvite.trim() || null,
          professional_id: ordreInvite.trim() || null,
          validity_days: 14,
        });
      setLienEmis(emise);
      setLibelle(""); setNomInvite(""); setOrdreInvite("");
      setRevision((n) => n + 1);
    } catch (cause) {
      setErreur(String(cause));
    } finally {
      setEnCours(false);
    }
  }

  async function revoquer(invitationId: string) {
    setEnCours(true);
    setErreur(null);
    try {
      await revoquerInvitation(auth.porteur, organisation.organization_id,
                               invitationId);
      setRevision((n) => n + 1);
    } catch (cause) {
      setErreur(String(cause));
    } finally {
      setEnCours(false);
    }
  }

  async function changer(userId: string, modification: MembreModification) {
    setEnCours(true);
    setErreur(null);
    try {
      await modifierMembre(auth.porteur, organisation.organization_id,
                           userId, modification);
      setRevision((n) => n + 1);
    } catch (cause) {
      setErreur(String(cause));
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div id="equipe">
      <h3>Équipe de {organisation.name}</h3>
      {erreur && <p role="alert">{erreur}</p>}

      <table id="table-membres">
        <thead>
          <tr>
            <th>Nom professionnel</th><th>Rôle</th><th>Inscription</th>
            <th>État</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {(membres ?? []).map((m) => (
            <tr key={m.user_id} data-membre={m.user_id}>
              <td>{m.display_name ?? <em>— aucun —</em>}</td>
              <td data-role={m.role}>{m.role}</td>
              <td>{m.professional_id ?? "—"}</td>
              <td data-actif={m.is_active ? "oui" : "non"}>
                {m.is_active ? "actif" : "révoqué"}
              </td>
              <td>
                {m.is_me ? (
                  // AUCUN BOUTON SUR SA PROPRE LIGNE, ET LA RAISON EST DITE.
                  // La base refuse de toute façon: montrer un bouton qui
                  // recevra un refus est pire que ne pas le montrer.
                  <span className="aide">
                    vous — on ne modifie pas sa propre adhésion
                  </span>
                ) : (
                  <>
                    <select aria-label={`Rôle de ${m.display_name ?? m.user_id}`}
                            value={m.role} disabled={enCours}
                            onChange={(e) => changer(m.user_id,
                              { role: e.target.value, is_active: null,
                                display_name: null, professional_id: null,
                                update_names: false })}>
                      {ROLES.map((r) => (
                        <option key={r} value={r}>{r}</option>
                      ))}
                    </select>
                    <button type="button" disabled={enCours}
                            data-action={m.is_active ? "desactiver" : "reactiver"}
                            onClick={() => changer(m.user_id,
                              { role: null, is_active: !m.is_active,
                                display_name: null, professional_id: null,
                                update_names: false })}>
                      {m.is_active ? "Désactiver" : "Réactiver"}
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="aide">
        Une adhésion désactivée <strong>ne disparaît pas</strong>&nbsp;: une note
        de dix ans doit rester lisible et nommer son signataire. Ce qui
        disparaît, c&apos;est l&apos;accès.
      </p>

      <form onSubmit={inviter} id="formulaire-invitation">
        <fieldset>
          <legend>Inviter quelqu&apos;un</legend>
          <div className="grille">
            <div>
              <label htmlFor="role-invite">Rôle</label>
              <select id="role-invite" value={role}
                      onChange={(e) => setRole(e.target.value)}>
                {ROLES.map((r) => (
                  <option key={r} value={r}>{r} — {ROLE_EXPLIQUE[r]}</option>
                ))}
              </select>
              {organisation.member_role === "admin" && role === "owner" && (
                <span className="aide" id="admin-pas-owner">
                  Un «&nbsp;admin&nbsp;» ne peut pas inviter un
                  «&nbsp;owner&nbsp;»&nbsp;: il donnerait plus que son propre
                  pouvoir. La base refusera.
                </span>
              )}
            </div>
            <div>
              <label htmlFor="libelle-invite">Aide-mémoire (facultatif)</label>
              <input id="libelle-invite" value={libelle}
                     onChange={(e) => setLibelle(e.target.value)} />
              <span className="aide">
                Pour vous y retrouver. Aucune adresse électronique n&apos;est
                demandée ni stockée.
              </span>
            </div>
            <div>
              <label htmlFor="nom-invite">Nom professionnel de l&apos;invité</label>
              <input id="nom-invite" value={nomInvite}
                     onChange={(e) => setNomInvite(e.target.value)} />
              <span className="aide">
                Posé par vous, pas par l&apos;invité&nbsp;: quelqu&apos;un qui
                choisirait ce nom pourrait attester sous celui d&apos;un autre.
              </span>
            </div>
            <div>
              <label htmlFor="ordre-invite">
                Numéro d&apos;inscription (facultatif)
              </label>
              <input id="ordre-invite" value={ordreInvite}
                     onChange={(e) => setOrdreInvite(e.target.value)} />
            </div>
          </div>
          <button type="submit" id="emettre-invitation" disabled={enCours}>
            {enCours ? "Émission…" : "Émettre le lien"}
          </button>
        </fieldset>
      </form>

      {lienEmis && (
        <div id="lien-emis" role="status">
          <p>
            <strong>Copiez ce lien maintenant.</strong> Il n&apos;existe nulle
            part ailleurs&nbsp;— la base n&apos;en connaît que l&apos;empreinte —
            et il ne sera pas réaffiché. Il expire le{" "}
            {lienEmis.expires_at.slice(0, 10)}.
          </p>
          <input id="secret-invitation" readOnly value={lienEmis.token}
                 onFocus={(e) => e.currentTarget.select()} />
        </div>
      )}

      <table id="table-invitations">
        <thead>
          <tr>
            <th>Rôle</th><th>Aide-mémoire</th><th>État</th><th>Expire</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {(invitations ?? []).map((i) => (
            <tr key={i.invitation_id} data-invitation={i.invitation_id}>
              <td>{i.role}</td>
              <td>{i.label ?? "—"}</td>
              <td data-etat={i.state}>{i.state}</td>
              <td>{i.expires_at.slice(0, 10)}</td>
              <td>
                {i.state === "pending" ? (
                  <button type="button" disabled={enCours}
                          data-action="revoquer"
                          onClick={() => revoquer(i.invitation_id)}>
                    Révoquer
                  </button>
                ) : (
                  // UNE INVITATION CONSOMMEE NE SE REVOQUE PAS: retirer le
                  // lien ne retirerait personne du bureau, et laisserait
                  // croire le contraire.
                  <span className="aide">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * L'historique du projet, et la réouverture d'un calcul sauvegardé.
 *
 * LES REFUS Y FIGURENT, et c'est le point. Un historique qui ne montrerait que
 * les calculs aboutis ferait croire qu'aucun n'a jamais été refusé — or c'est
 * la première trace qu'un audit cherche.
 *
 * ROUVRIR NE RECALCULE RIEN. Le serveur rend ce qui a été enregistré ; relancer
 * le moteur donnerait le résultat d'aujourd'hui pour un calcul d'hier.
 */
//: LA MATRICE, TELLE QUE L'ECRAN LA LIT.
//:
//: ELLE NE PROTEGE RIEN. La frontiere est dans `project_exiger_capacite()`
//: (0023), qui refuse quel que soit l'appelant, et la route la rejoue avant
//: de deposer le moindre octet. Ce qui est ici decide seulement de ce qu'on
//: MONTRE — et de ce qu'on EXPLIQUE quand on ne montre pas.
const REDACTEURS = ["owner", "admin", "engineer"];

function peutRediger(p: Projet): boolean {
  return p.member_active !== false && REDACTEURS.includes(p.member_role);
}

function peutValider(p: Projet): boolean {
  return p.member_active !== false
    && p.member_role === "validating_engineer";
}

function Historique({ projet, revision, surReouverture, surLivrable }: {
  projet: Projet;
  revision: number;
  surReouverture: (issue: Issue) => void;
  surLivrable: () => void;
}) {
  const auth = useAuth();
  const [lignes, setLignes] = useState<CalculResume[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    let vivant = true;
    historiqueDuProjet(auth.porteur, projet.project_id)
      .then((h) => { if (vivant) { setLignes(h.calculations); setErreur(null); } })
      .catch((cause) => {
        if (vivant) { setLignes(null); setErreur(String(cause)); }
      });
    return () => { vivant = false; };
  }, [auth.porteur, projet.project_id, revision]);

  async function rouvrir(calculationId: string) {
    try {
      surReouverture(issueDepuisEnregistre(
        await rouvrirCalcul(auth.porteur, projet.project_id, calculationId)));
    } catch (cause) {
      surReouverture(issueDepuisErreur(cause));
    }
  }

  /**
   * Télécharge la note du calcul choisi.
   *
   * L'ERREUR EST AFFICHEE, PAS AVALEE. Un calcul refusé n'a pas de note — le
   * serveur répond 422 en le disant — et un téléchargement qui échoue en
   * silence laisserait l'ingénieur attendre un fichier qui n'arrivera pas.
   */
  async function telecharger(calculationId: string) {
    try {
      await telechargerNote(auth.porteur, projet.project_id, calculationId);
      setErreur(null);
    } catch (cause) {
      setErreur(cause instanceof AppelRefuse
        ? `${cause.statut} — la note n'a pas pu etre produite.`
        : String(cause));
    }
  }

  /**
   * Produit un brouillon de livrable depuis le calcul choisi.
   *
   * LE 503 EST DISTINGUE DU 422, et l'ecran le dit differemment. « Aucun
   * magasin d'objets n'est declare » n'est pas un refus de la demande: il n'y
   * a rien a corriger dans la demande, et inviter l'ingenieur a la reformuler
   * lui ferait perdre son temps.
   */
  async function produire(calculationId: string, format: "html" | "pdf") {
    try {
      await creerLivrable(auth.porteur, projet.project_id,
                          { calculation_id: calculationId, format });
      setErreur(null);
      surLivrable();
    } catch (cause) {
      setErreur(cause instanceof AppelRefuse
        ? (cause.statut === 503
            ? "503 — aucun magasin d'objets n'est disponible: le service ne "
              + "peut pas conserver les octets du livrable. Aucune ligne n'a "
              + "ete ecrite."
            : `${cause.statut} — ${cause.detail}`)
        : String(cause));
    }
  }

  return (
    <section className="bandeau">
      <strong>Historique — {projet.name}</strong>
      {erreur && <p role="alert">{erreur}</p>}
      {lignes !== null && lignes.length === 0 && (
        <p className="aide">Aucun calcul enregistré sur ce projet.</p>
      )}
      {lignes !== null && lignes.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Repère</th><th>État</th><th>Mode</th>
              <th>Utilisation max</th><th>Moteur</th><th></th>
            </tr>
          </thead>
          <tbody>
            {lignes.map((c) => (
              /* L'IDENTIFIANT DU CALCUL EST SUR LA LIGNE, et il sert.
                 Un historique de plusieurs calculs aboutis porte autant de
                 boutons identiques; sans repere, « cliquer sur Produire un
                 brouillon » ne designe rien de precis — ni pour un parcours
                 automatise, ni pour quelqu'un qui decrit ce qu'il a fait. */
              <tr key={c.calculation_id} data-calcul={c.calculation_id}>
                <td>{c.element ?? "—"}</td>
                <td>{c.status === "refused" ? "refusé" : "abouti"}</td>
                <td>{c.strict_ndp ? "strict" : "exploratoire"}</td>
                {/* `null` N'EST PAS `0`. Un refus n'a produit aucune
                    vérification, et « 0,00 » se lirait « largement vérifié »
                    là où rien ne l'a été. */}
                <td>{c.max_utilisation === null || c.max_utilisation === undefined
                      ? "—" : c.max_utilisation.toFixed(3)}</td>
                <td>{c.engine_version}</td>
                <td>
                  <button type="button"
                          onClick={() => rouvrir(c.calculation_id)}>
                    Rouvrir
                  </button>
                  {/* PAS DE NOTE POUR UN REFUS. Le moteur n'a rien conclu; un
                      bouton qui rendrait un 422 ferait chercher une panne la
                      ou il y a une reponse. Le motif est a la reouverture. */}
                  {c.status !== "refused" && (
                    <button type="button"
                            onClick={() => telecharger(c.calculation_id)}>
                      Télécharger la note HTML
                    </button>
                  )}
                  {/* LE BROUILLON N'EST PAS LA NOTE, ET LA DIFFERENCE COMPTE.
                      « Telecharger la note » rend un document a l'instant, qui
                      ne laisse aucune trace. « Produire un brouillon » ecrit un
                      LIVRABLE: ses octets sont deposes, relus, et leur
                      empreinte enregistree — c'est ce document-la, et pas un
                      autre, qu'un ingenieur pourra attester. */}
                  {/* DEUX BOUTONS, PARCE QU'IL Y A DEUX DOCUMENTS.
                      Le meme calcul, les memes chiffres, la meme mention
                      obligatoire: seule la forme du fichier change. Le HTML
                      s'ouvre hors ligne dans un navigateur; le PDF se joint a
                      un dossier. Aucun des deux n'est un brouillon "par
                      defaut" qu'on convertirait ensuite — chacun est un
                      livrable a part entiere, avec sa propre empreinte. */}
                  {c.status !== "refused" && peutRediger(projet) && (
                    <button type="button" id={`brouillon-html-${c.calculation_id}`}
                            onClick={() => produire(c.calculation_id, "html")}>
                      Produire un brouillon HTML
                    </button>
                  )}
                  {c.status !== "refused" && peutRediger(projet) && (
                    <button type="button" id={`brouillon-pdf-${c.calculation_id}`}
                            onClick={() => produire(c.calculation_id, "pdf")}>
                      Produire un brouillon PDF
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

/**
 * Les livrables du projet, et leur parcours de relecture.
 *
 * CE QUE CET ECRAN NE FAIT PAS
 * -----------------------------
 * Il ne DECIDE de rien. Le rôle de l'appelant, son nom et l'état de son
 * adhésion viennent du serveur, qui les dérive de `organization_members` sous
 * l'identité du jeton. L'écran s'en sert pour **montrer ou expliquer** ; la
 * frontière reste dans PostgreSQL, où elle est éprouvée. Cacher un bouton n'a
 * jamais protégé quoi que ce soit.
 *
 * AUCUN BOUTON DECORATIF
 * -----------------------
 * Chaque action affichée atteint une route réelle et survit au rechargement.
 * Quand une action est fermée, l'écran dit **pourquoi** plutôt que de faire
 * disparaître le bouton sans un mot : « votre rôle est dessinateur » se
 * comprend, un vide ne se comprend pas.
 *
 * CE QUE LE MOT « ATTESTER » VEUT DIRE ICI
 * -----------------------------------------
 * Une **attestation métier authentifiée**, jamais une signature électronique
 * qualifiée. Le produit enregistre qu'un membre actif, nommé, porteur du rôle
 * de validation, atteste avoir relu ce calcul-là. Le nom est le même ici, dans
 * l'API et dans PostgreSQL.
 */
const ETATS: Record<string, string> = {
  draft: "brouillon",
  review: "en relecture",
  validated: "validé",
  final: "émis",
};

function Livrables({ projet, revision, surChangement }: {
  projet: Projet;
  revision: number;
  surChangement: () => void;
}) {
  const auth = useAuth();
  const [lignes, setLignes] = useState<Livrable[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [ouvert, setOuvert] = useState<LivrableDetail | null>(null);
  const [motif, setMotif] = useState("");
  const [attestation, setAttestation] = useState("");
  const [reserves, setReserves] = useState("");
  const [enCours, setEnCours] = useState(false);

  //: L'HABILITATION VIENT DU SERVEUR, PAS DU NAVIGATEUR. Ces trois booléens ne
  //: protègent rien: ils décident de ce qu'on montre et de ce qu'on explique.
  const redacteur = peutRediger(projet);
  const validateur = peutValider(projet);
  const actif = projet.member_active !== false;

  useEffect(() => {
    let vivant = true;
    listerLivrables(auth.porteur, projet.project_id)
      .then((l) => { if (vivant) { setLignes(l); setErreur(null); } })
      .catch((cause) => {
        if (vivant) { setLignes(null); setErreur(String(cause)); }
      });
    return () => { vivant = false; };
  }, [auth.porteur, projet.project_id, revision]);

  /**
   * Exécute une action et rafraîchit. Le refus du serveur est AFFICHÉ TEL QUEL.
   *
   * LE MESSAGE DE POSTGRESQL EST LE BON MESSAGE. « le rôle "viewer" ne porte
   * pas la validation technique », « votre accès a été révoqué le … », « ce
   * calcul a été mené en mode non strict » : chacun dit exactement ce qui
   * bloque et ce qu'il faudrait pour le débloquer. Le remplacer par « action
   * impossible » perdrait tout ce qui rend le refus actionnable.
   */
  async function agir(quoi: () => Promise<LivrableDetail>) {
    setEnCours(true);
    try {
      setOuvert(await quoi());
      setErreur(null);
      surChangement();
    } catch (cause) {
      setErreur(cause instanceof AppelRefuse
        ? `${cause.statut} — ${cause.detail}` : String(cause));
    } finally {
      setEnCours(false);
    }
  }

  async function detailler(id: string) {
    try {
      setOuvert(await relireLivrable(auth.porteur, projet.project_id, id));
      setErreur(null);
    } catch (cause) {
      setErreur(String(cause));
    }
  }

  async function telecharger(id: string) {
    try {
      await telechargerLivrable(auth.porteur, projet.project_id, id);
      setErreur(null);
    } catch (cause) {
      setErreur(cause instanceof AppelRefuse
        ? `${cause.statut} — ${cause.detail}` : String(cause));
    }
  }

  /**
   * Le dossier de revue : le document ET ce a quoi il se rattache.
   *
   * ENVOYER LA NOTE SEULE OBLIGE SON DESTINATAIRE A CROIRE SUR PAROLE. Le
   * dossier porte, a cote des octets exacts, un manifeste qui nomme le
   * calcul, le contexte normatif, le SHA du moteur, l'identite d'execution,
   * les deux empreintes et l'attestation quand elle existe.
   */
  async function dossier(id: string) {
    try {
      await telechargerDossierDeRevue(auth.porteur, projet.project_id, id);
      setErreur(null);
    } catch (cause) {
      setErreur(cause instanceof AppelRefuse
        ? `${cause.statut} — ${cause.detail}` : String(cause));
    }
  }

  return (
    <section className="bandeau" id="livrables">
      <strong>Livrables — {projet.name}</strong>

      {/* POURQUOI LA VALIDATION EST FERMEE, DIT AVANT QU'ON L'ESSAIE.
          L'absence d'ingenieur habilite n'empeche ni les projets, ni les
          calculs, ni les brouillons: elle ferme l'attestation et l'emission,
          et c'est ce que cette ligne explique. */}
      {/* CE QUI EST OUVERT, ET CE QUI NE L'EST PAS, DIT AVANT QU'ON L'ESSAIE.
          Un bouton absent sans un mot ne s'explique pas; un bouton present
          qui rend un refus apprend a ignorer les messages d'erreur. */}
      {actif && redacteur && (
        <p className="aide" id="pourquoi-ferme">
          Vous êtes connecté comme <strong>{projet.member_role}</strong>
          {projet.member_name ? ` (${projet.member_name})` : ""} dans
          {" "}{projet.organization_name}. Produire un brouillon, le réviser et
          le soumettre à la relecture vous est ouvert ; le retour motivé,
          l&apos;attestation et l&apos;émission sont réservés au rôle{" "}
          <strong>validating_engineer</strong>, celui de l&apos;ingénieur qui
          répond de l&apos;étude.
        </p>
      )}
      {actif && validateur && (
        <p className="aide" id="pourquoi-ferme">
          Vous êtes connecté comme <strong>validating_engineer</strong>
          {projet.member_name ? ` (${projet.member_name})` : ""} dans
          {" "}{projet.organization_name}. Le retour motivé, l&apos;attestation
          et l&apos;émission vous reviennent. La rédaction d&apos;un brouillon
          revient aux rôles <strong>owner</strong>, <strong>admin</strong> et{" "}
          <strong>engineer</strong> : celui qui répond du calcul ne le rédige
          pas, et c&apos;est ce qui donne un sens à « relu ».
        </p>
      )}
      {actif && !redacteur && !validateur && (
        <p className="aide" id="pourquoi-ferme">
          Vous êtes connecté comme <strong>{projet.member_role}</strong>
          {projet.member_name ? ` (${projet.member_name})` : ""} dans
          {" "}{projet.organization_name}. Ce rôle donne accès à la lecture et
          au téléchargement. La rédaction revient aux rôles{" "}
          <strong>owner</strong>, <strong>admin</strong> et{" "}
          <strong>engineer</strong>, la validation au rôle{" "}
          <strong>validating_engineer</strong>.
        </p>
      )}
      {!actif && (
        <p className="aide" role="alert" id="pourquoi-ferme">
          Votre accès à {projet.organization_name} a été révoqué : il ne peut
          plus engager le bureau d&apos;études. Les livrables restent lisibles.
        </p>
      )}
      {validateur && actif && !projet.member_name && (
        <p className="aide" role="alert" id="pourquoi-ferme">
          Aucun nom n&apos;est enregistré pour votre adhésion. Une attestation
          porte le nom d&apos;une personne : l&apos;organisation doit le
          renseigner avant que la validation soit possible.
        </p>
      )}

      {erreur && <p role="alert" id="refus-livrable">{erreur}</p>}

      {lignes !== null && lignes.length === 0 && (
        <p className="aide">
          Aucun livrable. Produire un brouillon depuis un calcul abouti de
          l&apos;historique.
        </p>
      )}

      {lignes !== null && lignes.length > 0 && (
        <table id="table-livrables">
          <thead>
            <tr>
              <th>Document</th><th>État</th><th>Indice</th>
              <th>Filigrane</th><th>Validé par</th><th></th>
            </tr>
          </thead>
          <tbody>
            {lignes.map((d) => (
              <tr key={d.deliverable_id} data-livrable={d.deliverable_id}>
                <td>{d.filename}</td>
                <td data-etat={d.state}>{ETATS[d.state] ?? d.state}</td>
                <td>{d.revision}</td>
                {/* LE FILIGRANE DIT CE QUI EST VRAI DES OCTETS POUR TOUJOURS,
                    pas l'etat du workflow, qui change. Un document tire d'un
                    calcul non strict porte « PROJET — NON SIGNABLE » et le
                    portera encore dans dix ans. */}
                <td>{d.watermark ?? "—"}</td>
                <td>{d.validator_name ?? "—"}</td>
                <td>
                  <button type="button" onClick={() => detailler(d.deliverable_id)}>
                    Détail
                  </button>
                  <button type="button" onClick={() => telecharger(d.deliverable_id)}>
                    Télécharger
                  </button>
                  <button type="button" onClick={() => dossier(d.deliverable_id)}
                          title="Le document et son manifeste de rattachement">
                    Dossier de revue
                  </button>
                  {d.state === "draft" && redacteur && (
                    <button type="button" disabled={enCours}
                            onClick={() => agir(() => soumettreALaRelecture(
                              auth.porteur, projet.project_id, d.deliverable_id))}>
                      Soumettre à la relecture
                    </button>
                  )}
                  {d.state === "validated" && validateur && (
                    <button type="button" disabled={enCours}
                            onClick={() => agir(() => emettreLivrable(
                              auth.porteur, projet.project_id, d.deliverable_id))}>
                      Émettre
                    </button>
                  )}
                  {d.state === "final" && redacteur && (
                    <button type="button" disabled={enCours}
                            onClick={() => agir(() => reviserLivrable(
                              auth.porteur, projet.project_id, d.deliverable_id,
                              { calculation_id: d.calculation_id }))}
                            title="Un livrable émis ne se modifie plus: corriger, c'est émettre l'indice suivant.">
                      Créer une révision
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {ouvert && (
        <div className="bandeau" id="detail-livrable">
          <strong>{ouvert.filename} — indice {ouvert.revision}</strong>
          <dl>
            <dt>État</dt><dd>{ETATS[ouvert.state] ?? ouvert.state}</dd>
            <dt>Empreinte des octets</dt><dd><code>{ouvert.sha256}</code></dd>
            <dt>Taille</dt><dd>{ouvert.size_bytes} octets</dd>
            <dt>Moteur</dt>
            <dd>{ouvert.engine_version} — build{" "}
                <code>{ouvert.engine_build_sha ?? "—"}</code></dd>
            <dt>Identité d&apos;exécution</dt>
            <dd><code>{ouvert.execution_identity ?? "—"}</code></dd>
            <dt>Date normative</dt><dd>{ouvert.ndp_as_of ?? "—"}</dd>
            {ouvert.last_reason && (<>
              <dt>Dernier motif</dt><dd>{ouvert.last_reason}</dd>
            </>)}
            {ouvert.validator_name && (<>
              <dt>Attesté par</dt>
              <dd>{ouvert.validator_name} — {ouvert.validator_role}
                  {ouvert.professional_id ? ` — n° ${ouvert.professional_id}` : ""}
                  {ouvert.validated_at ? ` — ${ouvert.validated_at}` : ""}</dd>
              <dt>Attestation</dt><dd>{ouvert.statement}</dd>
            </>)}
            {ouvert.reservations && (<>
              <dt>Réserves du validateur</dt><dd>{ouvert.reservations}</dd>
            </>)}
          </dl>

          <strong>Historique</strong>
          <ol id="historique-livrable">
            {(ouvert.transitions ?? []).map((t, i) => (
              <li key={i}>
                {t.occurred_at} — {t.from_state ? `${ETATS[t.from_state] ?? t.from_state} → ` : ""}
                {ETATS[t.to_state] ?? t.to_state}
                {t.reason ? ` — ${t.reason}` : ""}
              </li>
            ))}
          </ol>

          {/* LE RETOUR AU BROUILLON EXIGE UN MOTIF, ICI COMME EN BASE. Le
              champ n'est pas une politesse: celui qui reprend le document doit
              savoir ce qui lui est reproche. */}
          {ouvert.state === "review" && validateur && (
            <p>
              <label htmlFor="motif-retour">Motif du retour au brouillon</label>
              <input id="motif-retour" type="text" value={motif}
                     onChange={(e) => setMotif(e.target.value)}
                     placeholder="Ce qui est reproché à la pièce" />
              <button type="button" disabled={enCours || !motif.trim()}
                      onClick={() => agir(() => renvoyerAuBrouillon(
                        auth.porteur, projet.project_id, ouvert.deliverable_id,
                        { reason: motif }))}>
                Renvoyer au brouillon
              </button>
            </p>
          )}

          {/* LE PANNEAU D'ATTESTATION N'APPARAIT QUE POUR UN COMPTE HABILITE.
              Et quand il n'apparait pas, la ligne d'explication plus haut dit
              pourquoi — un bouton absent sans un mot ne s'explique pas. */}
          {ouvert.state === "review" && validateur && (
            <div id="panneau-attestation">
              <strong>Attestation métier authentifiée</strong>
              <p className="aide">
                Ce n&apos;est pas une signature électronique qualifiée. Vous
                attestez, sous votre nom et votre inscription professionnelle,
                avoir relu ce calcul-là — ses entrées, son instantané normatif,
                son identité d&apos;exécution et l&apos;empreinte des octets
                ci-dessus.
              </p>
              <label htmlFor="attestation">Ce que vous attestez</label>
              <textarea id="attestation" value={attestation} rows={3}
                        onChange={(e) => setAttestation(e.target.value)} />
              <label htmlFor="reserves">Réserves (facultatif)</label>
              <textarea id="reserves" value={reserves} rows={2}
                        onChange={(e) => setReserves(e.target.value)} />
              <button type="button" disabled={enCours || !attestation.trim()}
                      onClick={() => agir(() => attesterLivrable(
                        auth.porteur, projet.project_id, ouvert.deliverable_id,
                        { statement: attestation,
                          reservations: reserves.trim() || null }))}>
                Attester ce calcul
              </button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

/**
 * Où en est le référentiel national du pays choisi.
 *
 * POURQUOI CE BANDEAU EXISTE
 * ---------------------------
 * Jusqu'ici, la seule façon d'apprendre qu'aucun calcul strict ne peut aboutir
 * pour un pays était de **saisir une poutre et de lire le 422**. C'est une
 * mauvaise façon de poser la question : « où en est la Belgique ? » se pose
 * avant qu'aucune poutre n'existe, et la réponse sert à toutes les études.
 *
 * Il ne bloque rien. Si l'API ne répond pas, il disparaît, et l'écran de
 * calcul reste utilisable.
 */
/**
 * LE DIAGNOSTIC QUAND L'ADRESSE DE L'API N'A PAS ETE DECLAREE.
 *
 * Il y avait un repli codé en dur sur `http://127.0.0.1:8000`. Une image
 * déployée sans `EUROSTRUCT_API_URL` appelait donc le port 8000 du poste de
 * **l'utilisateur** : cela échoue chez lui, réussit chez un développeur qui a
 * une API locale, et n'apparaît dans aucun journal serveur. Le défaut de
 * configuration pouvait durer des semaines.
 *
 * Le repli est parti. À sa place, cette bannière — et chaque appel refuse en
 * nommant la variable manquante.
 *
 * `useEffect` PLUTOT QU'UNE LECTURE AU RENDU: la configuration est déposée
 * dans la page par un script du layout, et le rendu serveur ne la voit pas.
 * La lire pendant le rendu ferait diverger serveur et client — l'erreur
 * d'hydratation #418, qui remplacerait ce diagnostic par un autre.
 */
function ConfigurationManquante() {
  const [manque, setManque] = useState(false);
  useEffect(() => { setManque(!apiUrlConfiguree()); }, []);
  if (!manque) return null;
  return (
    <div className="bandeau refus" role="alert" id="configuration-absente">
      <strong>Configuration absente</strong> — {DIAGNOSTIC_API_ABSENTE}
    </div>
  );
}

function Referentiel({ pays, revision = 0 }:
                     { pays: string; revision?: number }) {
  const [etat, setEtat] = useState<EtatReferentiel | null>(null);

  useEffect(() => {
    let vivant = true;
    setEtat(null);
    etatDuReferentiel(pays).then((e) => {
      // La reponse d'un pays qu'on a quitte entre-temps ne doit pas s'afficher.
      if (vivant) setEtat(e);
    });
    return () => {
      vivant = false;
    };
    // `revision` CHANGE APRES UNE CONSOMMATION: le bandeau redemande alors
    // l'etat au lieu d'afficher indefiniment celui d'avant la decision.
  }, [pays, revision]);

  if (!etat) return null;

  const confirmes = etat.referentiel.confirmed ?? 0;
  const total = etat.referentiel.total ?? 0;
  // LE BANDEAU SUIT LE PREFLIGHT, PAS LE COMPTE. Un seul paramètre confirmé
  // sur les huit que le calcul demande laisse le calcul impossible: c'est
  // `strict_ndp_satisfied` qui le dit, jamais `confirmed > 0`.
  const pret = etat.strict_ndp_satisfied;

  return (
    <div className={pret ? "bandeau ok" : "bandeau alerte"} role="status">
      <strong>Référentiel {etat.country_code}</strong> — {confirmes} / {total}{" "}
      valeur(s) nationale(s) confirmée(s) au {etat.as_of}.
      {!pret && (
        <>
          {" "}Le calcul en mode strict reste impossible pour ce pays :
          {" "}{etat.blocking.length} des {etat.required.length} paramètres
          qu&apos;il demande ne sont pas utilisables. Une valeur transcrite
          n&apos;est pas une valeur validée.
          <div className="clause" style={{ marginTop: ".4rem" }}>{etat.action}</div>
        </>
      )}
      <PlanDeChargeRepli pays={etat.country_code} total={total} />
    </div>
  );
}

/**
 * Les paramètres, un par un. Replié par défaut, chargé à l'ouverture.
 *
 * POURQUOI UN REPLI, ET PAS UNE LISTE TOUJOURS VISIBLE
 * -----------------------------------------------------
 * Le bandeau répond à « peut-on signer ? » en une ligne. Vingt-neuf fiches
 * au-dessus du formulaire répondraient à une autre question, que personne n'a
 * posée en arrivant sur un écran de calcul.
 *
 * La requête part **à l'ouverture**, pas au rendu : payer vingt-neuf fiches
 * pour un repli que l'on n'ouvre pas, c'est payer pour rien.
 */
function PlanDeChargeRepli({ pays, total }: { pays: string; total: number }) {
  const [plan, setPlan] = useState<PlanDeCharge | null>(null);
  const [charge, setCharge] = useState(false);

  async function ouvrir(e: React.SyntheticEvent<HTMLDetailsElement>) {
    if (!e.currentTarget.open || charge) return;
    setCharge(true);
    setPlan(await planDeCharge(pays));
  }

  return (
    <details style={{ marginTop: ".5rem" }} onToggle={ouvrir}>
      <summary>Voir les {total} paramètres et ce qui reste à faire</summary>
      {charge && !plan && (
        <p className="clause">Le plan de charge n&apos;a pas pu être chargé.</p>
      )}
      {plan && (
        <ul className="bloquants">
          {plan.parameters.map((p) => (
            <li key={p.key}>
              <div><strong>{p.parameter_name}</strong> — {p.description}</div>
              <div className="clause">
                {p.standard} {p.clause} · {p.national_annex_reference}
                {p.source_page ? ` · p. ${p.source_page}` : ""}
              </div>
              <div className="clause">
                {p.usable_in_strict_mode
                  ? "confirmé — utilisable en mode strict"
                  : p.reste_a_faire}
              </div>
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}


/**
 * La connexion Supabase, quand elle est configurée.
 *
 * ELLE NE GARDE PAS LE CALCUL. Le calcul EC2 est déterministe et ne consulte
 * aucune donnée d'autorité : le protéger derrière une authentification
 * n'apporterait rien, et rendrait la tranche inutilisable pour évaluer le
 * moteur. Ce sont les **décisions d'autorité** qui exigent une identité.
 *
 * ELLE NE DÉTIENT PLUS LA SESSION. Elle la demande au fournisseur — c'est tout
 * l'objet du correctif : une session détenue ici n'était visible de personne,
 * et le jeton obtenu ne servait à rien.
 *
 * Quand la configuration est absente, ce bloc dit pourquoi, et n'affiche
 * aucun formulaire dont on saurait d'avance qu'il refusera.
 */
function Connexion() {
  const auth = useAuth();
  const [courriel, setCourriel] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [refus, setRefus] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  if (!auth.disponible) {
    return (
      <div className="bandeau alerte" role="status">
        <strong>Authentification non configurée</strong>
        Le calcul ci-dessous fonctionne : il est déterministe et ne consulte
        aucune donnée d&apos;autorité. Les décisions d&apos;autorité, elles,
        exigent une identité vérifiée — voir <code>eurostruct/api/.env.example</code>.
        <div style={{ marginTop: ".35rem" }}>
          <code>SUPABASE_UNVERIFIED</code>
        </div>
      </div>
    );
  }

  if (auth.connecte) {
    return (
      <div className="bandeau ok" role="status">
        <strong>Session ouverte</strong>
        Le jeton vit en mémoire dans cet onglet, jamais dans{" "}
        <code>localStorage</code>, <code>sessionStorage</code>, un cookie ou une
        URL. Fermer l&apos;onglet le fait disparaître.
        <div style={{ marginTop: ".6rem" }}>
          <button id="deconnecter" type="button" className="secondaire"
                  onClick={auth.fermer}>
            Se déconnecter
          </button>
        </div>
      </div>
    );
  }

  async function connecter(e: React.FormEvent) {
    e.preventDefault();
    setEnCours(true);
    setRefus(null);
    // LE MOT DE PASSE QUITTE L'ETAT REACT AVANT MEME L'ALLER-RETOUR.
    //
    // Il y restait pour toute la durée de la session: visible dans l'arbre
    // React, dans un instantané des outils de développement, dans un rapport
    // d'erreur qui sérialise l'état, et dans la mémoire de l'onglet bien
    // après qu'il ait servi. Il n'a qu'UN usage, et cet usage est ici.
    //
    // La copie locale est celle qui part; l'état, lui, est vidé tout de suite.
    const secret = motDePasse;
    setMotDePasse("");
    setRefus(await auth.ouvrir(courriel, secret));
    setEnCours(false);
  }

  return (
    <form onSubmit={connecter}>
      <fieldset>
        <legend>Connexion</legend>
        {auth.expiree && (
          <p id="session-expiree" className="bandeau refus" role="alert">
            <strong>Session expirée</strong> — elle n&apos;a pas pu être
            renouvelée. Aucune requête n&apos;a été envoyée avec le jeton
            périmé. Reconnectez-vous.
          </p>
        )}
        <div className="grille">
          <div>
            <label htmlFor="courriel">Courriel</label>
            <input id="courriel" type="email" autoComplete="username"
                   value={courriel}
                   onChange={(e) => setCourriel(e.target.value)} />
          </div>
          <div>
            <label htmlFor="mdp">Mot de passe</label>
            <input id="mdp" type="password" autoComplete="current-password"
                   value={motDePasse}
                   onChange={(e) => setMotDePasse(e.target.value)} />
          </div>
        </div>
        <button id="connecter" type="submit" className="secondaire"
                disabled={enCours} style={{ marginTop: ".8rem" }}>
          {enCours ? "Connexion…" : "Se connecter"}
        </button>
        {refus && (
          <p className="clause" style={{ marginTop: ".6rem" }}>{refus}</p>
        )}
      </fieldset>
    </form>
  );
}

/** Ce qu'une étape d'autorité a répondu. Jamais un résultat partiel. */
type Etape = { nom: string; statut: string; detail: string };

/**
 * LES DÉCISIONS D'AUTORITÉ : composer, proposer, relire, approuver, consommer.
 *
 * POURQUOI CETTE SECTION EXISTE
 * ------------------------------
 * Le quatre-yeux était complet côté PostgreSQL et côté API, et **inatteignable
 * depuis l'écran**. Une règle que l'interface ne sait pas exercer n'est pas une
 * règle du produit : c'est une règle du dépôt.
 *
 * CE QU'ELLE NE FAIT PLUS
 * ------------------------
 * Elle proposait `EN 1992-1-1:alpha_cc`, édition `2004`, motif fixe — écrits
 * dans ce fichier. Aucun de ces trois-là n'était vrai : l'édition belge en
 * vigueur n'est pas `2004`, si bien que la proposition échouait sur la portée
 * d'habilitation avant d'atteindre quoi que ce soit d'intéressant. Un écran
 * qui ne peut proposer qu'une seule chose, et la mauvaise, ne rend pas la
 * règle exerçable.
 *
 * LE PARAMÈTRE VIENT DU PLAN DE CHARGE, la liste que l'API rend pour le pays.
 * L'ingénieur en choisit un.
 *
 * LE NAVIGATEUR NE CONSTRUIT AUCUNE EMPREINTE NORMATIVE. Il envoie ce que la
 * personne a relevé dans l'annexe publiée — la citation, le folio, ce qu'elle
 * déclare avoir contrôlé — et le **serveur** compose les quatre payloads
 * canoniques et leurs empreintes. La valeur, l'unité, la provenance, la
 * clause et l'empreinte du document viennent du registre, jamais de l'écran.
 *
 * L'IDENTIFIANT SURVIT À LA DÉCONNEXION, LE JETON NON. Le premier est une
 * référence de dossier — B en a besoin, et peut le coller ici. Le second est
 * l'identité de A, et elle part avec lui.
 *
 * B RELIT LE DOSSIER GELÉ AVANT D'APPROUVER. Son navigateur n'a jamais vu ce
 * que A a composé ; sans la relecture, approuver serait cliquer sur un numéro.
 *
 * AUCUN CHAMP D'ACTEUR. Ni ici, ni dans le corps envoyé : l'identité sort du
 * jeton porteur. Le contrat serveur est `extra="forbid"`, si bien qu'un champ
 * ajouté ferait un 422 plutôt qu'une usurpation.
 */
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function DecisionsAutorite(
  { pays, surConsommation }: { pays: Pays; surConsommation?: () => void },
) {
  const auth = useAuth();
  //: L'ETAT DU DOSSIER VIT ICI, hors du bloc de connexion: se déconnecter ne
  //: doit pas effacer le numéro que le second ingénieur doit reprendre.
  const [decision, setDecision] = useState<string>("");
  const [etapes, setEtapes] = useState<Etape[]>([]);
  const [enCours, setEnCours] = useState(false);

  const [candidats, setCandidats] = useState<ParametreNdp[] | null>(null);
  const [cle, setCle] = useState<string>("");
  const [citation, setCitation] = useState<string>("");
  const [folio, setFolio] = useState<string>("");
  const [declaration, setDeclaration] = useState<string>("");
  const [dossier, setDossier] = useState<AuthorityReviewDossier | null>(null);
  const [relu, setRelu] = useState<AuthorityDecisionReview | null>(null);

  //: LE PLAN DE CHARGE, CHARGE PAR PAYS. Il est PUBLIC — le referentiel
  //: national est le meme pour tout le monde — donc il se charge sans jeton,
  //: et l'ecran sait quoi proposer avant meme qu'une session existe.
  useEffect(() => {
    let vivant = true;
    setCandidats(null);
    setCle("");
    setDossier(null);
    planDeCharge(pays).then((plan) => {
      if (!vivant) return;
      setCandidats(plan ? plan.parameters : []);
    });
    return () => { vivant = false; };
  }, [pays]);

  if (!auth.disponible) return null;

  const noter = (nom: string, statut: string, detail: string) =>
    setEtapes((e) => [...e, { nom, statut, detail }]);

  /** Exécute une étape et note ce qu'elle a répondu. Ne masque aucun refus. */
  async function etape(nom: string, action: () => Promise<string>) {
    setEnCours(true);
    try {
      noter(nom, "ok", await action());
    } catch (cause) {
      if (cause instanceof SessionExpiree) {
        // RIEN N'EST PARTI. C'est le fait à afficher: pas « le serveur a
        // refusé », mais « nous n'avons pas envoyé ».
        noter(nom, "non envoyé", cause.message);
      } else if (cause instanceof AppelRefuse) {
        noter(nom, `refus ${cause.statut}`, cause.detail);
      } else {
        noter(nom, "panne", String(cause));
      }
    } finally {
      setEnCours(false);
    }
  }

  const choisi = (candidats ?? []).find((p) => p.key === cle) ?? null;
  //: UN PARAMETRE SANS EMPREINTE DE DOCUMENT NE PEUT PORTER AUCUNE
  //: CONFIRMATION: on ne le propose pas, plutot que de laisser composer un
  //: dossier que le serveur refusera.
  const proposables = (candidats ?? []).filter(
    (p) => !p.usable_in_strict_mode && p.source_doc_id);
  const dossierPret = Boolean(
    choisi?.source_doc_id && citation.trim() && declaration.trim());
  const idValide = UUID.test(decision.trim());

  async function composer(): Promise<string> {
    if (!choisi?.source_doc_id) throw new Error("aucun parametre choisi.");
    const compose = await composerDossier(auth.porteur, {
      country_code: choisi.country_code,
      rule_id: choisi.key,
      statement: declaration.trim(),
      // NI `implementation_note`, NI `effect`. Les deux entraient dans un
      // payload canonique, donc dans une empreinte: une phrase choisie par
      // l'ecran deplacait le sujet signe. L'effet se derive du registre et
      // l'empreinte d'implementation du code deploye — ni l'un ni l'autre ne
      // passe plus par ici.
      citations: [{
        document_digest: choisi.source_doc_id,
        quote: citation.trim(),
        page_printed: Number(folio) || choisi.source_page || 1,
      }],
    });
    setDossier(compose);
    return compose.digests.normative_spec_digest ?? "compose";
  }

  return (
    <section>
      <fieldset>
        <legend>Décisions d&apos;autorité</legend>
        <p className="aide">
          Une confirmation de valeur nationale exige <strong>deux</strong>
          {" "}ingénieurs : celui qui propose ne peut pas approuver. Le second
          reprend l&apos;identifiant ci-dessous après s&apos;être connecté à sa
          propre session, <strong>relit le dossier gelé</strong>, puis approuve.
        </p>

        <div>
          <label htmlFor="param-autorite">Paramètre à faire confirmer</label>
          <select id="param-autorite" value={cle} disabled={enCours}
                  onChange={(e) => { setCle(e.target.value); setDossier(null); }}>
            <option value="">
              {candidats === null
                ? "chargement du plan de charge…"
                : proposables.length === 0
                  ? "aucun paramètre à confirmer pour ce pays"
                  : "— choisir —"}
            </option>
            {proposables.map((p) => (
              <option key={p.key} value={p.key}>
                {p.parameter_name} — {p.standard} {p.clause}
              </option>
            ))}
          </select>
        </div>

        {choisi && (
          <>
            <div className="clause" style={{ marginTop: ".4rem" }}>
              {choisi.national_annex_reference} · éd. {choisi.edition}
              {choisi.source_page ? ` · p. ${choisi.source_page}` : ""}
              {" · "}valeur au registre : {String(choisi.parameter_value)}
              {" "}{choisi.unit}
            </div>
            <div className="grille" style={{ marginTop: ".5rem" }}>
              <div>
                <label htmlFor="citation">
                  Citation relevée dans l&apos;annexe publiée
                </label>
                <input id="citation" value={citation} disabled={enCours}
                       onChange={(e) => {
                         setCitation(e.target.value); setDossier(null);
                       }} />
              </div>
              <div>
                <label htmlFor="folio">Folio imprimé</label>
                <input id="folio" inputMode="numeric" value={folio}
                       disabled={enCours}
                       placeholder={String(choisi.source_page ?? 1)}
                       onChange={(e) => {
                         setFolio(e.target.value); setDossier(null);
                       }} />
              </div>
              <div>
                <label htmlFor="declaration">Ce que vous certifiez avoir lu</label>
                <input id="declaration" value={declaration} disabled={enCours}
                       onChange={(e) => {
                         setDeclaration(e.target.value); setDossier(null);
                       }} />
              </div>
            </div>
            <button id="composer" type="button" className="secondaire"
                    disabled={enCours || !dossierPret}
                    style={{ marginTop: ".5rem" }}
                    onClick={() => etape("composition", composer)}>
              Composer le dossier (le serveur le fabrique)
            </button>
          </>
        )}

        {dossier && <Dossier resume={dossier.summary}
                             empreintes={dossier.digests} titre="Dossier composé" />}

        <p style={{ marginTop: ".6rem" }}>
          Décision en cours :{" "}
          <code id="decision-id">{decision || "—"}</code>
        </p>
        <div>
          <label htmlFor="reprendre-decision">
            Reprendre une décision (second ingénieur)
          </label>
          <input id="reprendre-decision" value={decision} disabled={enCours}
                 placeholder="identifiant reçu du premier ingénieur"
                 onChange={(e) => { setDecision(e.target.value); setRelu(null); }} />
        </div>

        <div className="grille" style={{ marginTop: ".5rem" }}>
          <button id="proposer" type="button" className="secondaire"
                  disabled={enCours || !dossier}
                  onClick={() => etape("proposition", async () => {
                    if (!dossier || !choisi) throw new Error("aucun dossier.");
                    // LE CORPS PORTE LE DOSSIER TEL QUE LE SERVEUR L'A RENDU.
                    // Le navigateur ne le retouche pas: il ne saurait pas
                    // recalculer les empreintes, et c'est voulu.
                    const proposition: AuthorityDecisionRequest = {
                      subject_kind: "ndp_parameter",
                      subject_id: choisi.key,
                      org_id: null,
                      country_code: choisi.country_code,
                      standard_family: choisi.standard_family,
                      part: choisi.part,
                      edition: choisi.edition,
                      permission: "can_validate_normative_reference",
                      reason: declaration.trim(),
                      review_package: dossier.package,
                    };
                    const cree = await proposerDecision(auth.porteur, proposition);
                    setDecision(cree.decision_id);
                    setRelu(null);
                    return cree.decision_id;
                  })}>
            1. Proposer
          </button>
          <button id="relire" type="button" className="secondaire"
                  disabled={enCours || !idValide}
                  onClick={() => etape("relecture", async () => {
                    const d = await relireDecision(auth.porteur, decision.trim());
                    setRelu(d);
                    return `${d.subject_id} — ${d.state}`;
                  })}>
            2. Relire le dossier gelé
          </button>
          <button id="approuver" type="button" className="secondaire"
                  disabled={enCours || !idValide}
                  onClick={() => etape("approbation", async () => {
                    await approuverDecision(auth.porteur, decision.trim());
                    return "approuvee";
                  })}>
            3. Approuver (second ingénieur)
          </button>
          <button id="consommer" type="button" className="secondaire"
                  disabled={enCours || !idValide}
                  onClick={() => etape("consommation", async () => {
                    const c = await consommerDecision(auth.porteur,
                                                      decision.trim());
                    // LE BANDEAU DU REFERENTIEL EST PERIME DES CET INSTANT.
                    // Sans ce signal il continuerait d'afficher le compte
                    // d'avant — le seul effet visible du parcours resterait
                    // invisible.
                    if (c.consumed) surConsommation?.();
                    return c.consumed ? "consommee" : "non consommee";
                  })}>
            4. Consommer
          </button>
        </div>

        {relu && (
          <Dossier resume={{
            rule_id: relu.subject_id,
            country_code: relu.country_code,
            standard_family: relu.standard_family,
            part: relu.part,
            edition: relu.edition,
            etat: relu.state,
            proposee_le: relu.proposed_at,
            declaration: relu.package?.statement ?? "",
          }} empreintes={relu.digests ?? {}}
             titre="Dossier gelé, relu depuis la base" />
        )}

        {etapes.length > 0 && (
          <ul className="bloquants" id="journal-autorite">
            {etapes.map((e, i) => (
              <li key={i}>
                <strong>{e.nom}</strong> — {e.statut}
                <div className="clause">{e.detail}</div>
              </li>
            ))}
          </ul>
        )}
      </fieldset>
    </section>
  );
}

/**
 * Le dossier, affiché tel que le serveur l'a rendu.
 *
 * IL N'EN CALCULE RIEN. Ni empreinte, ni résumé : les deux arrivent du serveur,
 * qui les a produits sur le contenu qu'il conserve.
 */
function Dossier({ resume, empreintes, titre }: {
  resume: Record<string, unknown>;
  empreintes: Record<string, string>;
  titre: string;
}) {
  return (
    <div className="bandeau" style={{ marginTop: ".6rem" }} role="status"
         data-dossier={titre}>
      <strong>{titre}</strong>
      <ul className="bloquants">
        {Object.entries(resume).map(([k, v]) => (
          <li key={k}><code>{k}</code> : {String(v)}</li>
        ))}
      </ul>
      <div className="clause">
        {Object.entries(empreintes).map(([k, v]) => (
          <div key={k}><code>{k}</code> : {v.slice(0, 16)}…</div>
        ))}
      </div>
    </div>
  );
}

/** Un refus est une liste de travail, pas une page d'erreur. */
function Refus({ issue }: { issue: Extract<Issue, { type: "refus" }> }) {
  const { erreur } = issue.valeur;
  const bloquants: BlockingParameterDTO[] = erreur.preflight?.blocking ?? [];

  return (
    <section>
      <div className="bandeau refus" role="alert">
        <strong>
          Calcul refusé — {erreur.what}
        </strong>
        {erreur.error === "national_annex_incomplete"
          ? "Le référentiel national n'est pas complet. Ce n'est pas une panne : " +
            "tant qu'une valeur n'a pas été relevée dans l'Annexe Nationale " +
            "publiée, le moteur refuse de l'utiliser."
          : erreur.detail}
      </div>

      {bloquants.length > 0 && (
        <>
          <h2>
            {bloquants.length} paramètre(s) à faire relever
          </h2>
          <ul className="bloquants">
            {bloquants.map((p) => (
              <li key={p.key}>
                <code>{p.key}</code>
                <div className="clause">
                  {p.clause} — {p.national_annex_reference}
                </div>
                <div className="clause">{p.detail}</div>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

/** Les trois seuls statuts du contrat, en clair. */
const STATUT_LISIBLE: Record<string, string> = {
  pass: "vérifié",
  fail: "NON VÉRIFIÉ",
  not_applicable: "sans objet",
};

function Resultat({ issue }: { issue: Extract<Issue, { type: "resultat" }> }) {
  const r = issue.valeur;
  const res = r.result;
  const checks = r.verification?.checks ?? [];

  return (
    <section>
      {r.exploratory && (
        <div className="bandeau alerte" role="status">
          <span className="mention-non-signable">
            {r.mention ?? "PROJET — NON SIGNABLE"}
          </span>
          <div style={{ marginTop: ".5rem" }}>{r.avertissement}</div>
        </div>
      )}

      {/* La mention obligatoire vient de la REPONSE, jamais d'une chaine
          recopiee ici: une seconde redaction divergerait de celle que porte
          le DXF, et l'ecran affirmerait autre chose que le livrable. */}
      <p className="pied" style={{ marginTop: 0 }}>{r.notice}</p>

      <h2>Résultat</h2>
      <div className="cartes">
        <Carte cle="A_s requise" valeur={res.As_required.value}
               unite="mm²" decimales={0} />
        <Carte cle="M_Rd" valeur={res.M_Rd.value} unite="kN·m" decimales={1} />
        <Carte cle="Utilisation" valeur={res.utilisation * 100} unite="%"
               decimales={1} />
        <Carte cle="Bras de levier z" valeur={res.z.value} unite="mm"
               decimales={0} />
      </div>

      {checks.length > 0 && (
        <>
          <h2>Vérifications</h2>
          <table>
            <thead>
              <tr>
                <th>Vérification</th>
                <th>Statut</th>
                <th className="nombre">Utilisation</th>
                <th>Clause</th>
              </tr>
            </thead>
            <tbody>
              {checks.map((c, i) => (
                <tr key={i}>
                  <td>{c.name}</td>
                  <td>{STATUT_LISIBLE[c.status] ?? c.status}</td>
                  <td className="nombre">
                    {(c.utilisation * 100).toLocaleString("fr-BE", {
                      minimumFractionDigits: 1, maximumFractionDigits: 1,
                    })} %
                  </td>
                  {/* `cite` EST LA REFERENCE CITABLE, telle que le moteur la
                      compose. L'interface ne recompose pas une reference a
                      partir de `standard` et `clause`: elle affiche celle qui
                      ira dans la note. */}
                  <td className="clause">{c.clause.cite}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <Ferraillage calcul={issue.requete} />
    </section>
  );
}

/**
 * Le plan de section.
 *
 * LE FERRAILLAGE EST SAISI, PAS DEDUIT. `As_required` dit combien d'acier il
 * faut ; il ne dit pas en combien de barres, de quel diamètre, ni comment
 * elles sont disposées. Choisir à la place de l'ingénieur produirait un plan
 * que personne n'a décidé.
 */
/**
 * Le plan de section, produit **depuis la requête qui vient d'être vérifiée**.
 *
 * CE QUI ÉTAIT FAUX, ET CE QUE ÇA DONNAIT
 * ----------------------------------------
 * Ce composant fabriquait sa propre géométrie — `b: 300, h: 500` en dur, plus
 * des barres supérieures et un espacement de cadres que personne n'avait
 * choisis. Une poutre calculée en 250 × 600 sortait cotée 300 × 500, sous le
 * repère de l'élément et avec la mention légale : un plan crédible d'une
 * poutre jamais vérifiée.
 *
 * Le composant ne connaît plus aucune dimension. Il reçoit `calcul`, la
 * requête gelée au moment du calcul, et n'y ajoute que ce que l'ingénieur
 * choisit vraiment : les barres et l'enrobage. Le moteur revérifie la section
 * ainsi ferraillée, et **refuse de dessiner** si elle ne passe pas.
 */
function Ferraillage({ calcul }: { calcul: Ec2BeamFlexureRequest }) {
  const [nb, setNb] = useState("3");
  const [diam, setDiam] = useState("16");
  const [enrobage, setEnrobage] = useState("30");
  const [diamCadre, setDiamCadre] = useState("8");
  const [espCadre, setEspCadre] = useState("200");
  const [etat, setEtat] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  async function telecharger() {
    setEnCours(true);
    setEtat(null);
    // La géométrie n'est PAS reconstruite ici: elle voyage dans `calcul`.
    const requete: Ec2BeamSectionRequest = {
      calculation: calcul,
      reinforcement: {
        cover: Number(enrobage),
        link_diameter: Number(diamCadre),
        link_spacing: Number(espCadre),
        bottom: [{ count: Number(nb), diameter: Number(diam), mark: "A1" }],
      },
    };
    const issue = await telechargerDxf(requete);
    setEtat(
      issue.ok
        ? `Plan téléchargé: ${calcul.element || "section"}.dxf`
        : issue.message,
    );
    setEnCours(false);
  }

  return (
    <>
      <h2>Plan de section (DXF)</h2>
      <p className="clause">
        Le ferraillage est <strong>choisi</strong>, pas déduit du calcul : la
        section d&apos;acier requise ne dit ni le nombre de barres ni leur
        diamètre.
      </p>
      <div className="grille" style={{ marginBottom: ".75rem" }}>
        <div>
          <label htmlFor="nb">Barres inférieures</label>
          <input id="nb" inputMode="numeric" value={nb}
                 onChange={(e) => setNb(e.target.value)} />
        </div>
        <div>
          <label htmlFor="diam">Diamètre (mm)</label>
          <input id="diam" inputMode="decimal" value={diam}
                 onChange={(e) => setDiam(e.target.value)} />
        </div>
        <div>
          <label htmlFor="enr">Enrobage c<sub>nom</sub> (mm)</label>
          <input id="enr" inputMode="decimal" value={enrobage}
                 onChange={(e) => setEnrobage(e.target.value)} />
        </div>
        <div>
          <label htmlFor="dcad">Cadres Ø (mm)</label>
          <input id="dcad" inputMode="decimal" value={diamCadre}
                 onChange={(e) => setDiamCadre(e.target.value)} />
        </div>
        <div>
          <label htmlFor="ecad">Espacement cadres (mm)</label>
          <input id="ecad" inputMode="decimal" value={espCadre}
                 onChange={(e) => setEspCadre(e.target.value)} />
        </div>
      </div>
      <button type="button" className="secondaire" onClick={telecharger}
              disabled={enCours}>
        {enCours ? "Génération…" : "Télécharger le DXF"}
      </button>
      {etat && <p className="clause" style={{ marginTop: ".6rem" }}>{etat}</p>}
    </>
  );
}

function Carte({ cle, valeur, unite, decimales }: {
  cle: string; valeur: number; unite: string; decimales: number;
}) {
  return (
    <div className="carte">
      <div className="cle">{cle}</div>
      <div className="valeur">
        {valeur.toLocaleString("fr-BE", {
          minimumFractionDigits: decimales,
          maximumFractionDigits: decimales,
        })}
        <span className="unite"> {unite}</span>
      </div>
    </div>
  );
}
