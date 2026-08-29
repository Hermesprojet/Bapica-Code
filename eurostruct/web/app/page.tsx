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
import { useState } from "react";
import type { BlockingParameterDTO } from "@contracts/generated/engine";
import { urlDxf, verifierFlexion, type Issue } from "@/lib/api";

type Champs = {
  b: string; h: string; d: string; M_Ed: string;
  beton: string; acier: string; pays: string; element: string;
  strict: boolean;
};

const DEFAUTS: Champs = {
  b: "300", h: "500", d: "450", M_Ed: "150",
  beton: "C25/30", acier: "B500B", pays: "BE", element: "P1",
  strict: true,
};

export default function Page() {
  const [champs, setChamps] = useState<Champs>(DEFAUTS);
  const [issue, setIssue] = useState<Issue | null>(null);
  const [enCours, setEnCours] = useState(false);

  const majuscule = (k: keyof Champs) => (e: { target: { value: string } }) =>
    setChamps((c) => ({ ...c, [k]: e.target.value }));

  async function soumettre(e: React.FormEvent) {
    e.preventDefault();
    setEnCours(true);
    setIssue(null);
    const resultat = await verifierFlexion({
      project_id: "DEMO-001",
      element: champs.element,
      country: champs.pays as never,
      strict_ndp: champs.strict,
      M_Ed: { value: Number(champs.M_Ed), unit: "kN*m" },
      section: {
        b: { value: Number(champs.b), unit: "mm" },
        h: { value: Number(champs.h), unit: "mm" },
        d: { value: Number(champs.d), unit: "mm" },
      },
      materials: { concrete_grade: champs.beton, steel_grade: champs.acier },
    } as never);
    setIssue(resultat);
    setEnCours(false);
  }

  return (
    <main>
      <h1>EUROSTRUCT — flexion simple, section rectangulaire</h1>
      <p className="sous-titre">
        Vérification ELU selon EN 1992-1-1 et son Annexe Nationale.
      </p>

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
              <select id="pays" value={champs.pays} onChange={majuscule("pays")}>
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
        Un résultat n&apos;est signable que si les paramètres nationaux
        utilisés sont confirmés. Aucun calcul ne remplace la validation d&apos;un
        ingénieur.
      </p>
    </main>
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
      {!r.signable && (
        <div className="bandeau alerte" role="status">
          <span className="mention-non-signable">
            {r.mention ?? "PROJET — NON SIGNABLE"}
          </span>
          <div style={{ marginTop: ".5rem" }}>{r.avertissement}</div>
        </div>
      )}

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

      <h2>Plan de ferraillage</h2>
      <p className="clause">
        Le DXF est servi par <code>{urlDxf()}</code>. Le tracé exige un
        ferraillage choisi ; il n&apos;est pas déduit du calcul.
      </p>
    </section>
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
