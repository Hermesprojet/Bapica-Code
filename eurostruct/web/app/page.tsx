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
  type PlanDeCharge,
} from "@/lib/api";
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

  const majuscule = (k: keyof Champs) => (e: { target: { value: string } }) =>
    setChamps((c) => ({ ...c, [k]: e.target.value }));

  // Le sélecteur ne peut rendre que les quatre pays du contrat: on le dit au
  // typage plutôt que de le supposer.
  const changerPays = (e: { target: { value: string } }) =>
    setChamps((c) => ({ ...c, pays: e.target.value as Pays }));

  async function soumettre(e: React.FormEvent) {
    e.preventDefault();
    setEnCours(true);
    setIssue(null);
    // Une requête RÉELLEMENT typée: si le contrat change, ceci ne compile plus.
    const requete: Ec2BeamFlexureRequest = {
      project_id: "DEMO-001",
      element: champs.element,
      country: champs.pays,
      strict_ndp: champs.strict,
      M_Ed: { value: Number(champs.M_Ed), unit: "kN*m" },
      section: {
        b: { value: Number(champs.b), unit: "mm" },
        h: { value: Number(champs.h), unit: "mm" },
        d: { value: Number(champs.d), unit: "mm" },
      },
      materials: { concrete_grade: champs.beton, steel_grade: champs.acier },
    };
    const resultat = await verifierFlexion(requete);
    setIssue(resultat);
    setEnCours(false);
  }

  return (
    <main>
      <h1>EUROSTRUCT — flexion simple, section rectangulaire</h1>
      <p className="sous-titre">
        Vérification ELU selon EN 1992-1-1 et son Annexe Nationale.
      </p>

      <ConfigurationManquante />
      <Connexion />
      <DecisionsAutorite pays={champs.pays}
                         surConsommation={() => setRevision((n) => n + 1)} />
      <Referentiel pays={champs.pays} revision={revision} />

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
              <select id="pays" value={champs.pays} onChange={changerPays}>
                <option value="BE">Belgique</option>
                <option value="FR">France</option>
                <option value="ES">Espagne</option>
                <option value="DE">Allemagne</option>
              </select>
            </div>
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
          {enCours ? "Calcul en cours…" : "Vérifier"}
        </button>
      </form>

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
      implementation_note:
        `lecture scalaire de ${choisi.key} depuis le registre national`,
      effect: `fixe la valeur nationale de ${choisi.parameter_name}`,
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
