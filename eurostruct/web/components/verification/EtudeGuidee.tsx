"use client";

/**
 * La vérification complète d'une poutre, en sept étapes.
 *
 * POURQUOI SEPT ÉTAPES PLUTÔT QU'UN FORMULAIRE
 * ----------------------------------------------
 * L'étude demande dix-sept entrées. Posées d'un bloc, deux d'entre elles se
 * font remplir sans y penser — `phi_creep` et le système structural — parce
 * qu'elles ressemblent à des réglages alors que ce sont des décisions : entre
 * une console (K = 0,4) et une travée intermédiaire (K = 1,5) il y a un
 * facteur presque quatre sur la dispense de flèche.
 *
 * Les étapes servent donc à une chose précise : rendre visible ce qui n'est
 * PAS rempli, étape par étape, plutôt que de laisser l'ingénieur découvrir au
 * 422 qu'il manquait un champ à l'autre bout de la page.
 *
 * CET ÉCRAN NE CALCULE RIEN, ET N'A AUCUNE RÈGLE D'INGÉNIERIE
 * ------------------------------------------------------------
 * Pas une formule, pas un arrondi, pas une borne. Il ne vérifie même pas que
 * `d < h` : cette question-là a des réponses nationales, et un second juge
 * dans le navigateur serait un juge que personne ne relit. Il vérifie
 * seulement qu'une valeur a été SAISIE, et laisse le serveur refuser avec sa
 * clause et son annexe.
 *
 * LE RÉFÉRENTIEL N'EST PAS UN CHAMP. Pays, région et date d'application sont
 * figés sur le projet ; l'étape 1 les AFFICHE, en lecture seule, parce que
 * masquer le référentiel appliqué serait pire que de le montrer inerte.
 */
import { useMemo, useState } from "react";
import {
  CHAMPS_INITIAUX, ETAPES, EXPOSITIONS, SYSTEMES,
  champsManquants, enRequete, etudeComplete,
  type ChampsEtude, type CleEtape,
} from "./champs";
import type { Projet } from "@/lib/atelier";

/**
 * Ce que le parent doit fournir.
 *
 * `surEtude` reçoit l'étude ENREGISTRÉE, pas les champs saisis : l'écran
 * n'affiche jamais un résultat qu'il aurait composé lui-même.
 */
export function EtudeGuidee({ projet, enCours, surLancer, motifImpossible }: {
  projet: Projet | null;
  enCours: boolean;
  surLancer: (requete: ReturnType<typeof enRequete>) => void;
  //: Un motif venu du parent — session absente, droits insuffisants. Il
  //: s'ajoute aux champs manquants plutôt que de les remplacer: l'ingénieur a
  //: droit aux deux raisons, pas à la première qu'on a trouvée.
  motifImpossible?: string | null;
}) {
  const [champs, setChamps] = useState<ChampsEtude>(CHAMPS_INITIAUX);
  const [etape, setEtape] = useState(0);
  //: L'EXPLORATOIRE EST UN CHOIX EXPLICITE, PAS UNE CASE OUBLIÉE. Décocher le
  //: mode strict demande une confirmation, parce que le résultat qui en sort
  //: ne peut JAMAIS être finalisé — pas même après correction.
  const [exploratoireAssume, setExploratoireAssume] = useState(false);

  const manquants = useMemo(() => champsManquants(champs), [champs]);
  const complet = etudeComplete(champs);
  const majuscule = (k: keyof ChampsEtude) => (e: { target: { value: string } }) =>
    setChamps((c) => ({ ...c, [k]: e.target.value }));

  /**
   * Pourquoi le lancement est impossible — ou `null`.
   *
   * UN BOUTON GRIS SANS EXPLICATION EST UNE IMPASSE. L'écran dit ce qui
   * manque et où, dans l'ordre où on peut y remédier.
   */
  function motifDeBlocage(): string | null {
    if (motifImpossible) return motifImpossible;
    if (!projet) {
      return "Aucun projet sélectionné. Une vérification complète s'enregistre "
        + "sur un dossier : c'est lui qui fixe le pays, la région et la date "
        + "d'application de l'Annexe Nationale.";
    }
    const incompletes = ETAPES
      .filter((e) => manquants[e.cle].length > 0)
      .map((e) => `${e.titre} (${manquants[e.cle].join(", ")})`);
    if (incompletes.length) {
      return `Étapes incomplètes — ${incompletes.join(" ; ")}.`;
    }
    if (!champs.strict && !exploratoireAssume) {
      return "Le mode exploratoire n'a pas été confirmé. Cochez la case de "
        + "l'étape 7, ou remettez le mode strict.";
    }
    return null;
  }

  const blocage = motifDeBlocage();

  function lancer() {
    if (blocage) return;
    surLancer(enRequete(champs));
  }

  const courante = ETAPES[etape];

  return (
    <section aria-labelledby="titre-etude">
      <h2 id="titre-etude">Vérification complète d&apos;une poutre</h2>
      <p className="aide">
        Cinq chapitres — flexion, effort tranchant, ancrage, ouverture des
        fissures, flèche — vérifiés en une seule saisie, sous l&apos;Annexe
        Nationale du projet.
      </p>

      {/* LE FIL DES ÉTAPES. Il montre l'avancement ET les manques: une étape
          traversée sans être remplie ne doit pas ressembler à une étape
          faite. */}
      <ol className="etapes" aria-label="Étapes de la saisie">
        {ETAPES.map((e, i) => {
          const vide = manquants[e.cle].length > 0;
          return (
            <li key={e.cle}>
              <button type="button"
                      className={"etape"
                        + (i === etape ? " active" : "")
                        + (vide ? " incomplete" : " remplie")}
                      aria-current={i === etape ? "step" : undefined}
                      onClick={() => setEtape(i)}
                      title={vide
                        ? `Manque : ${manquants[e.cle].join(", ")}`
                        : "Étape complète"}>
                <span className="rang">{i + 1}</span>
                <span className="titre">{e.titre}</span>
              </button>
            </li>
          );
        })}
      </ol>

      <fieldset>
        <legend>{etape + 1}. {courante.titre}</legend>

        {courante.cle === "dossier" && (
          <EtapeDossier projet={projet} champs={champs} majuscule={majuscule} />
        )}
        {courante.cle === "section" && (
          <EtapeSection champs={champs} majuscule={majuscule} />
        )}
        {courante.cle === "materiaux" && (
          <EtapeMateriaux champs={champs} majuscule={majuscule} />
        )}
        {courante.cle === "sollicitations" && (
          <EtapeSollicitations champs={champs} majuscule={majuscule} />
        )}
        {courante.cle === "ferraillage" && (
          <EtapeFerraillage champs={champs} majuscule={majuscule} />
        )}
        {courante.cle === "service" && (
          <EtapeService champs={champs} majuscule={majuscule}
                        surCase={(v) => setChamps((c) =>
                          ({ ...c, cloisons_fragiles: v }))} />
        )}
        {courante.cle === "mode" && (
          <EtapeMode champs={champs} assume={exploratoireAssume}
                     surStrict={(v) => {
                       setChamps((c) => ({ ...c, strict: v }));
                       if (v) setExploratoireAssume(false);
                     }}
                     surAssume={setExploratoireAssume} />
        )}

        {manquants[courante.cle].length > 0 && (
          <p className="aide manque" role="status">
            À renseigner : {manquants[courante.cle].join(", ")}.
          </p>
        )}
      </fieldset>

      <div className="navigation-etapes">
        <button type="button" className="secondaire" disabled={etape === 0}
                onClick={() => setEtape((n) => Math.max(0, n - 1))}>
          Précédent
        </button>
        <button type="button" className="secondaire"
                disabled={etape === ETAPES.length - 1}
                onClick={() =>
                  setEtape((n) => Math.min(ETAPES.length - 1, n + 1))}>
          Suivant
        </button>
        <button type="button" disabled={enCours || !!blocage} onClick={lancer}
                title={blocage ?? "Enregistre l'étude sur le projet"}>
          {enCours ? "Vérification en cours…" : "Vérifier les cinq chapitres"}
        </button>
      </div>

      {/* LE MOTIF EST ÉCRIT, PAS SEULEMENT SURVOLÉ. Une infobulle ne se lit
          pas au clavier et ne s'imprime pas. */}
      {blocage && (
        <p className="aide manque" role="status">{blocage}</p>
      )}
      {!blocage && !champs.strict && (
        <p className="bandeau alerte" role="status">
          <strong>Étude exploratoire</strong>
          Elle sera enregistrée et lisible, mais elle ne pourra jamais être
          finalisée : le résultat portera la mention{" "}
          <strong>PROJET — NON SIGNABLE</strong>.
        </p>
      )}
      {!blocage && complet && champs.strict && (
        <p className="aide">
          Mode strict : un paramètre national non confirmé bloquera{" "}
          <em>avant</em> le calcul, et rien ne sera enregistré.
        </p>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// LES SEPT ÉTAPES. Chacune est un composant, pour qu'aucune ne puisse en lire
// une autre: une étape qui dériverait une valeur d'une voisine recréerait
// exactement la seconde source qu'on refuse au serveur.
// ---------------------------------------------------------------------------
type Passeur = (k: keyof ChampsEtude) =>
  (e: { target: { value: string } }) => void;

function EtapeDossier({ projet, champs, majuscule }: {
  projet: Projet | null; champs: ChampsEtude; majuscule: Passeur;
}) {
  return (
    <>
      <div className="grille">
        <div>
          <label htmlFor="vc-element">Repère de l&apos;élément</label>
          <input id="vc-element" value={champs.element}
                 onChange={majuscule("element")} />
          <span className="aide">Il figurera sur la note et sur le plan.</span>
        </div>
        <div>
          <label htmlFor="vc-referentiel">Référentiel du projet</label>
          <input id="vc-referentiel" readOnly
                 value={projet
                   ? `${projet.country}`
                     + `${projet.region ? " — " + projet.region : ""}`
                     + ` — ${projet.ndp_as_of}`
                   : "aucun projet sélectionné"} />
          <span className="aide">
            Figé à la création du projet. Il résout l&apos;édition
            d&apos;Annexe Nationale applicable, et aucun calcul du dossier ne
            peut en désigner une autre.
          </span>
        </div>
      </div>
      {!projet && (
        <p className="aide manque" role="status">
          Sélectionnez un projet dans l&apos;atelier ci-dessus. Sans dossier,
          il n&apos;y a pas de référentiel — donc pas de vérification
          opposable.
        </p>
      )}
    </>
  );
}

function EtapeSection({ champs, majuscule }: {
  champs: ChampsEtude; majuscule: Passeur;
}) {
  return (
    <div className="grille">
      <div>
        <label htmlFor="vc-b">Largeur b (mm)</label>
        <input id="vc-b" inputMode="decimal" value={champs.b}
               onChange={majuscule("b")} />
      </div>
      <div>
        <label htmlFor="vc-h">Hauteur h (mm)</label>
        <input id="vc-h" inputMode="decimal" value={champs.h}
               onChange={majuscule("h")} />
      </div>
      <div>
        <label htmlFor="vc-d">Hauteur utile d (mm)</label>
        <input id="vc-d" inputMode="decimal" value={champs.d}
               onChange={majuscule("d")} />
        <span className="aide">
          Du bord comprimé au centre de gravité des aciers tendus.
        </span>
      </div>
      <div>
        <label htmlFor="vc-leff">Portée utile l<sub>eff</sub> (mm)</label>
        <input id="vc-leff" inputMode="decimal" value={champs.l_eff}
               onChange={majuscule("l_eff")} />
        <span className="aide">
          §5.3.2.2. Elle décide de la dispense du calcul de flèche.
        </span>
      </div>
    </div>
  );
}

function EtapeMateriaux({ champs, majuscule }: {
  champs: ChampsEtude; majuscule: Passeur;
}) {
  return (
    <div className="grille">
      <div>
        <label htmlFor="vc-beton">Béton</label>
        <input id="vc-beton" value={champs.beton} onChange={majuscule("beton")} />
        <span className="aide">Désignation du Tableau 3.1, p. ex. C30/37.</span>
      </div>
      <div>
        <label htmlFor="vc-acier">Acier</label>
        <input id="vc-acier" value={champs.acier} onChange={majuscule("acier")} />
      </div>
      <div>
        <label htmlFor="vc-expo">Classe d&apos;exposition</label>
        <select id="vc-expo" value={champs.exposition}
                onChange={majuscule("exposition")}>
          {EXPOSITIONS.map((x) => <option key={x} value={x}>{x}</option>)}
        </select>
        <span className="aide">
          Tableau 4.1. Elle choisit la ligne de w<sub>max</sub> et la branche
          de §7.2(2) : c&apos;est un jugement sur l&apos;environnement, que la
          géométrie ne révèle pas.
        </span>
      </div>
    </div>
  );
}

function EtapeSollicitations({ champs, majuscule }: {
  champs: ChampsEtude; majuscule: Passeur;
}) {
  return (
    <>
      <div className="grille">
        <div>
          <label htmlFor="vc-med">M<sub>Ed</sub> (kN·m)</label>
          <input id="vc-med" inputMode="decimal" value={champs.M_Ed}
                 onChange={majuscule("M_Ed")} />
          <span className="aide">Combinaison fondamentale, ELU.</span>
        </div>
        <div>
          <label htmlFor="vc-ved">V<sub>Ed</sub> (kN)</label>
          <input id="vc-ved" inputMode="decimal" value={champs.V_Ed}
                 onChange={majuscule("V_Ed")} />
        </div>
        <div>
          <label htmlFor="vc-mchar">M caractéristique (kN·m)</label>
          <input id="vc-mchar" inputMode="decimal" value={champs.M_char}
                 onChange={majuscule("M_char")} />
          <span className="aide">
            Sert à la limitation des contraintes, §7.2.
          </span>
        </div>
        <div>
          <label htmlFor="vc-mqp">M quasi-permanent (kN·m)</label>
          <input id="vc-mqp" inputMode="decimal" value={champs.M_qp}
                 onChange={majuscule("M_qp")} />
          <span className="aide">
            Sert à l&apos;ouverture des fissures, §7.3.
          </span>
        </div>
      </div>
      <p className="aide">
        Les quatre viennent de votre descente de charges. EUROSTRUCT ne les
        calcule pas et ne les déduit pas les uns des autres.
      </p>
    </>
  );
}

function EtapeFerraillage({ champs, majuscule }: {
  champs: ChampsEtude; majuscule: Passeur;
}) {
  return (
    <>
      <div className="grille">
        <div>
          <label htmlFor="vc-nb">Barres tendues — nombre</label>
          <input id="vc-nb" inputMode="numeric" value={champs.barres_nb}
                 onChange={majuscule("barres_nb")} />
        </div>
        <div>
          <label htmlFor="vc-phi">Barres tendues — diamètre (mm)</label>
          <input id="vc-phi" inputMode="decimal" value={champs.barres_diametre}
                 onChange={majuscule("barres_diametre")} />
        </div>
        <div>
          <label htmlFor="vc-branches">Cadres — branches</label>
          <input id="vc-branches" inputMode="numeric"
                 value={champs.cadres_branches}
                 onChange={majuscule("cadres_branches")} />
        </div>
        <div>
          <label htmlFor="vc-phiw">Cadres — diamètre (mm)</label>
          <input id="vc-phiw" inputMode="decimal" value={champs.cadres_diametre}
                 onChange={majuscule("cadres_diametre")} />
        </div>
        <div>
          <label htmlFor="vc-s">Cadres — espacement (mm)</label>
          <input id="vc-s" inputMode="decimal" value={champs.cadres_espacement}
                 onChange={majuscule("cadres_espacement")} />
        </div>
        <div>
          <label htmlFor="vc-enrobage">Enrobage (mm)</label>
          <input id="vc-enrobage" inputMode="decimal" value={champs.enrobage}
                 onChange={majuscule("enrobage")} />
        </div>
        <div>
          <label htmlFor="vc-cot">cot θ</label>
          <input id="vc-cot" inputMode="decimal" value={champs.cot_theta}
                 onChange={majuscule("cot_theta")} />
          <span className="aide">
            Inclinaison des bielles que vous retenez. Une borne nationale peut
            la refuser — et ce refus-là est juste.
          </span>
        </div>
        <div>
          <label htmlFor="vc-ancrage">Ancrage disponible (mm)</label>
          <input id="vc-ancrage" inputMode="decimal" value={champs.ancrage}
                 onChange={majuscule("ancrage")} />
          <span className="aide">
            La longueur dont vous disposez réellement à l&apos;about. Vous seul
            la connaissez.
          </span>
        </div>
        <div>
          <label htmlFor="vc-adherence">Conditions d&apos;adhérence</label>
          <select id="vc-adherence" value={champs.adherence}
                  onChange={majuscule("adherence")}>
            <option value="good">Bonnes (§8.4.2)</option>
            <option value="poor">Médiocres</option>
          </select>
        </div>
      </div>
      <p className="aide">
        L&apos;aire d&apos;acier n&apos;est pas saisie : elle se déduit des
        barres. Deux sources pour une même aire divergeraient un jour, et ce
        jour-là le plan montrerait autre chose que le calcul.
      </p>
    </>
  );
}

function EtapeService({ champs, majuscule, surCase }: {
  champs: ChampsEtude; majuscule: Passeur; surCase: (v: boolean) => void;
}) {
  return (
    <>
      <div className="grille">
        <div>
          <label htmlFor="vc-phicreep">Fluage φ(∞,t₀)</label>
          <input id="vc-phicreep" inputMode="decimal" value={champs.phi_creep}
                 onChange={majuscule("phi_creep")} placeholder="p. ex. 2,0" />
          <span className="aide">
            §3.1.4. Il dépend du rayon moyen, de l&apos;humidité et de
            l&apos;âge au chargement : aucun défaut n&apos;est proposé, parce
            qu&apos;un défaut passerait inaperçu.
          </span>
        </div>
        <div>
          <label htmlFor="vc-systeme">Système structural</label>
          <select id="vc-systeme" value={champs.systeme}
                  onChange={majuscule("systeme")}>
            <option value="">— à choisir —</option>
            {SYSTEMES.map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
          <span className="aide">
            Ligne du Tableau 7.4N. Entre une console et une travée
            intermédiaire, le rapport l/d admissible varie de près de quatre.
          </span>
        </div>
      </div>
      <div className="ligne-case">
        <input id="vc-cloisons" type="checkbox"
               checked={champs.cloisons_fragiles}
               onChange={(e) => surCase(e.target.checked)} />
        <label htmlFor="vc-cloisons">
          L&apos;élément porte des cloisons fragiles
          <span className="aide">
            Aucune géométrie ne le révèle : c&apos;est une donnée du projet,
            et elle durcit la limite de flèche.
          </span>
        </label>
      </div>
    </>
  );
}

function EtapeMode({ champs, assume, surStrict, surAssume }: {
  champs: ChampsEtude; assume: boolean;
  surStrict: (v: boolean) => void; surAssume: (v: boolean) => void;
}) {
  return (
    <>
      <div className="ligne-case">
        <input id="vc-strict" type="checkbox" checked={champs.strict}
               onChange={(e) => surStrict(e.target.checked)} />
        <label htmlFor="vc-strict">
          Mode strict — paramètres nationaux confirmés exigés
          <span className="aide">
            C&apos;est le défaut. Un paramètre non confirmé bloque{" "}
            <em>avant</em> le calcul, et rien n&apos;est enregistré : le refus
            porte la liste des paramètres à faire relever dans l&apos;Annexe
            Nationale publiée.
          </span>
        </label>
      </div>

      {!champs.strict && (
        <div className="bandeau alerte">
          <strong>Une étude exploratoire ne se finalise jamais</strong>
          Elle tourne avec des valeurs non confirmées. Elle sera enregistrée,
          lisible et rejouable — mais aucune correction de section ne la rendra
          signable : il faudra la relancer en mode strict, après confirmation
          des paramètres.
          <div className="ligne-case">
            <input id="vc-assume" type="checkbox" checked={assume}
                   onChange={(e) => surAssume(e.target.checked)} />
            <label htmlFor="vc-assume">
              J&apos;ai compris : cette étude servira au pré-dimensionnement,
              pas à une conclusion opposable.
            </label>
          </div>
        </div>
      )}
    </>
  );
}
