"use client";

/**
 * La revue des valeurs proposées : comparer, corriger, confirmer, rejeter,
 * reporter.
 *
 * CE QUE LA PERSONNE VOIT AVANT DE DÉCIDER
 * -----------------------------------------
 * La valeur proposée et la valeur retenue côte à côte, le texte lu tel quel,
 * la page, la méthode (couche texte, OCR, DXF) et sa confiance — indicative,
 * jamais une certitude —, l'origine de l'unité, et le champ de l'étude que la
 * valeur peut renseigner. Et le nom sous lequel elle décidera : celui que
 * l'organisation a enregistré, que l'écran ne fait qu'afficher.
 *
 * CE QUE L'ÉCRAN NE FAIT PAS
 * ---------------------------
 * Il ne pose ni nom ni date (le serveur le fait), ne convertit aucune unité
 * (le préremplissage arrive déjà dans l'unité du champ), et ne confirme rien
 * de lui-même : chaque décision est un geste, et elle est définitive.
 */
import { useEffect, useMemo, useState } from "react";
import type { Projet } from "@/lib/atelier";
import {
  confirmExtraction, enClairValeur, listExtractions, origineDeLUnite, prefill,
  type ChampPrerempli, type DocumentDepose, type Extraction, type Preremplissage,
} from "@/lib/documents";
import { AppelRefuse, type PorteurDeJeton } from "@/lib/transport";
import { enClair } from "@/lib/messages";

const STATUT_LISIBLE: Record<string, string> = {
  proposed: "À revoir", confirmed: "Confirmée", corrected: "Corrigée",
  rejected: "Rejetée",
};
const STATUT_CLASSE: Record<string, string> = {
  proposed: "attente", confirmed: "ok", corrected: "ok", rejected: "silence",
};
const METHODE_LISIBLE: Record<string, string> = {
  texte_natif: "couche texte", ocr: "OCR", dxf: "entité DXF", vision: "vision",
};

function enPhrase(cause: unknown): string {
  return cause instanceof AppelRefuse ? cause.detail : enClair(cause);
}

/** Un nombre si le texte en est un — la seule lecture que fait l'écran. */
function valeurSaisie(texte: string): number | string {
  const net = texte.trim().replace(",", ".");
  return net !== "" && Number.isFinite(Number(net)) ? Number(net) : texte.trim();
}

export function RevueExtractions({ projet, porteur, document, peutDecider,
                                   elementCourant, surDecision, surReport }: {
  projet: Projet; porteur: PorteurDeJeton; document: DocumentDepose | null;
  peutDecider: boolean; elementCourant: string;
  surDecision: () => void;
  surReport: (champs: ChampPrerempli[], resume: string) => void;
}) {
  //: `null` TANT QUE LA LISTE N'EST PAS REVENUE: un tableau vide dirait « rien
  //: n'a ete lu » pendant le chargement, et c'est faux.
  const [extractions, setExtractions] = useState<Extraction[] | null>(null);
  const [filtreStatut, setFiltreStatut] = useState("tous");
  const [filtreCategorie, setFiltreCategorie] = useState("toutes");
  const [correction, setCorrection] = useState<{ id: string; valeur: string;
                                                 unite: string; note: string } | null>(null);
  const [rejet, setRejet] = useState<{ id: string; note: string } | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; texte: string } | null>(null);
  const [preremplissage, setPreremplissage] = useState<Preremplissage | null>(null);
  const [enCours, setEnCours] = useState<string | null>(null);

  //: RELUE A L'OUVERTURE, PAS A CHAQUE DECISION. Une decision remplace sa
  //: ligne par celle que la base rend; relire toute la liste apres chaque clic
  //: ferait clignoter un tableau que l'ingenieur est en train de parcourir.
  const documentId = document?.document_id ?? null;
  useEffect(() => {
    if (!documentId) return;
    listExtractions(porteur, projet.project_id, documentId)
      .then(setExtractions)
      .catch((cause) => {
        setExtractions([]);
        setMessage({ ok: false, texte: enPhrase(cause) });
      });
  }, [porteur, projet.project_id, documentId]);

  const categories = useMemo(
    () => Array.from(new Map((extractions ?? []).map((x) => [x.kind, x.kind_label]))
      .entries()),
    [extractions]);
  const visibles = (extractions ?? []).filter(
    (x) => (filtreStatut === "tous" || x.status === filtreStatut)
      && (filtreCategorie === "toutes" || x.kind === filtreCategorie));

  //: LE NOM SOUS LEQUEL LA PERSONNE DECIDERA, tel que l'adhesion le porte.
  //: Absent, la base refusera: on le dit avant le clic plutot qu'apres.
  const nom = projet.member_name?.trim() || null;
  const motifSansDecision = !peutDecider
    ? `Votre rôle (« ${projet.member_role} ») permet de lire la revue, pas de décider.`
    : !nom
      ? "Aucun nom n'est enregistré pour votre adhésion : une décision porte le "
        + "nom d'une personne. Demandez à un administrateur du bureau de le "
        + "renseigner."
      : null;

  async function decider(x: Extraction, corps: Parameters<typeof confirmExtraction>[3]) {
    setEnCours(x.extraction_id);
    setMessage(null);
    try {
      const decidee = await confirmExtraction(porteur, projet.project_id,
                                              x.extraction_id, corps);
      setExtractions((liste) => (liste ?? []).map(
        (y) => (y.extraction_id === decidee.extraction_id ? decidee : y)));
      setCorrection(null);
      setRejet(null);
      surDecision();
    } catch (cause) {
      setMessage({ ok: false, texte: enPhrase(cause) });
    } finally {
      setEnCours(null);
    }
  }

  async function chargerPreremplissage(element: string): Promise<Preremplissage | null> {
    try {
      const p = await prefill(porteur, projet.project_id, element);
      setPreremplissage(p);
      return p;
    } catch (cause) {
      setMessage({ ok: false, texte: enPhrase(cause) });
      return null;
    }
  }

  /** Reporter UNE décision : la valeur convertie par le serveur, ou pourquoi pas. */
  async function reporterUne(x: Extraction) {
    const p = await chargerPreremplissage(x.element_label ?? elementCourant);
    if (!p) return;
    const candidats = [...p.fields, ...p.conflicts.flatMap((c) => c.candidates)];
    const champ = candidats.find((c) => c.extraction_id === x.extraction_id);
    if (champ) {
      surReport([champ], `« ${champ.label} » reporté depuis ${x.document_filename}, `
        + `page ${x.page}.`);
      setMessage({ ok: true, texte: `${champ.label} reporté dans l'étude : `
        + `${champ.value}${champ.unit ? " " + champ.unit : ""}.` });
      return;
    }
    const non = p.not_reportable.find((n) => n.extraction_id === x.extraction_id);
    setMessage({ ok: false, texte: non
      ? `Non reportée : ${non.reason}.`
      : "Cette valeur ne renseigne aucun champ de l'étude, ou elle concerne un "
        + "autre repère." });
  }

  /** Reporter TOUTES les décisions sans conflit pour le repère étudié. */
  async function reporterTout() {
    const p = await chargerPreremplissage(elementCourant);
    if (!p) return;
    if (!p.fields.length) {
      setMessage({ ok: false, texte: "Aucune valeur décidée ne se reporte sans "
        + "conflit pour ce repère." });
      return;
    }
    surReport(p.fields, `${p.fields.length} valeur(s) reportée(s) pour le repère `
      + `${elementCourant || "(aucun)"}`
      + (p.conflicts.length ? ` ; ${p.conflicts.length} champ(s) en conflit laissé(s) `
        + "à votre choix" : "") + ".");
    setMessage({ ok: true, texte: `${p.fields.length} valeur(s) reportée(s) dans l'étude.` });
  }

  if (!document) return null;
  return (
    <section className="revue" id="revue-extractions"
             aria-labelledby="titre-revue" data-document={document.document_id}>
      <h3 id="titre-revue">Revue des valeurs — {document.filename}</h3>
      <p className="aide">
        Les valeurs ci-dessous ont été <strong>lues</strong>, pas vérifiées.
        Confirmez celles qui sont justes, corrigez celles qui sont mal lues,
        rejetez les autres. Une décision est définitive et porte votre nom.
        {nom && peutDecider && (
          <> Vous décidez en tant que <strong id="revue-decideur">{nom}</strong> ;
            la date est posée par le serveur.</>
        )}
      </p>
      {motifSansDecision && (
        <p className="aide manque" id="revue-sans-decision" role="status">
          {motifSansDecision}
        </p>
      )}

      <div className="rangee-boutons filtres">
        <label htmlFor="revue-statut">Statut</label>
        <select id="revue-statut" value={filtreStatut}
                onChange={(e) => setFiltreStatut(e.target.value)}>
          <option value="tous">Tous</option>
          {Object.entries(STATUT_LISIBLE).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>))}
        </select>
        <label htmlFor="revue-categorie">Catégorie</label>
        <select id="revue-categorie" value={filtreCategorie}
                onChange={(e) => setFiltreCategorie(e.target.value)}>
          <option value="toutes">Toutes</option>
          {categories.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <button type="button" id="reporter-tout"
                onClick={() => void reporterTout()}
                title="Les valeurs confirmées ou corrigées, sans conflit, du repère saisi">
          Reporter dans l&apos;étude ({elementCourant || "tous repères"})
        </button>
      </div>

      {message && (
        <p className={"bandeau " + (message.ok ? "ok" : "refus")}
           id="revue-message" role={message.ok ? "status" : "alert"}>
          {message.texte}
        </p>
      )}

      {preremplissage && preremplissage.conflicts.length > 0 && (
        <div className="bandeau alerte" id="revue-conflits" role="status">
          <strong>Champs en conflit — à trancher</strong>
          <ul>
            {preremplissage.conflicts.map((c) => (
              <li key={c.path}>
                {c.label} : {c.candidates.map((x) => `${x.value}${x.unit ? " " + x.unit : ""}`
                  + (x.element_label ? ` (${x.element_label})` : "")).join(" ou ")}
                {" "}— reportez celle de l&apos;élément étudié ligne par ligne.
              </li>
            ))}
          </ul>
        </div>
      )}

      {extractions === null ? (
        <p className="aide" id="revue-chargement" role="status">
          Chargement des valeurs lues…
        </p>
      ) : (
        <>
          <div className="defilement">
            <table id="revue-tableau">
              <thead>
                <tr>
                  <th>Catégorie</th><th>Proposée</th><th>Retenue</th><th>Lu</th>
                  <th>Décision</th>
                </tr>
              </thead>
              <tbody>
                {visibles.map((x) => {
                  const unite = origineDeLUnite(x);
                  const occupe = enCours === x.extraction_id;
                  return (
                    <tr key={x.extraction_id} id={`extraction-${x.extraction_id}`}
                        data-categorie={x.kind} data-statut={x.status}>
                      <td>
                        {x.kind_label}
                        {x.element_label && <span className="etiquette">{x.element_label}</span>}
                        <span className="aide champ-etude">
                          {x.form_field_label ? `→ ${x.form_field_label}` : "→ aucun champ de l'étude"}
                        </span>
                      </td>
                      <td className="valeur-proposee">{enClairValeur(x.proposed_value)}</td>
                      <td className="valeur-retenue">{enClairValeur(x.final_value)}</td>
                      <td>
                        <q className="texte-lu">{x.raw_text}</q>
                        <span className="aide">
                          {" "}page {x.page} · {METHODE_LISIBLE[x.method] ?? x.method} ·
                          confiance {Math.round(x.confidence * 100)} %
                          {unite ? ` · unité ${unite}` : ""}
                        </span>
                        {x.form_warning && x.status !== "rejected" && (
                          <span className="aide manque"> {x.form_warning}</span>
                        )}
                      </td>
                      <td>
                        <span className={`etat ${STATUT_CLASSE[x.status] ?? "silence"}`}>
                          {STATUT_LISIBLE[x.status] ?? x.status}
                        </span>
                        {x.confirmed_by_name && (
                          <span className="aide decideur">
                            {" "}{x.confirmed_by_name}, {(x.confirmed_at ?? "").slice(0, 16)}
                          </span>
                        )}
                        {x.decision_note && <span className="aide"> — {x.decision_note}</span>}

                        {x.status === "proposed" && !motifSansDecision && (
                          <div className="rangee-boutons">
                            <button type="button" id={`confirmer-${x.extraction_id}`}
                                    disabled={occupe}
                                    onClick={() => void decider(x, { decision: "confirm" })}>
                              Confirmer
                            </button>
                            <button type="button" className="secondaire"
                                    id={`corriger-${x.extraction_id}`} disabled={occupe}
                                    onClick={() => setCorrection({
                                      id: x.extraction_id,
                                      valeur: String(x.proposed_value.value),
                                      unite: x.proposed_value.unit ?? "", note: "" })}>
                              Corriger
                            </button>
                            <button type="button" className="secondaire"
                                    id={`rejeter-${x.extraction_id}`} disabled={occupe}
                                    onClick={() => setRejet({ id: x.extraction_id, note: "" })}>
                              Rejeter
                            </button>
                          </div>
                        )}

                        {correction?.id === x.extraction_id && (
                          <div className="formulaire-decision">
                            <label htmlFor="correction-valeur">Valeur retenue</label>
                            <input id="correction-valeur" value={correction.valeur}
                                   onChange={(e) => setCorrection({ ...correction,
                                                                    valeur: e.target.value })} />
                            <label htmlFor="correction-unite">Unité (vide : sans unité)</label>
                            <input id="correction-unite" value={correction.unite}
                                   onChange={(e) => setCorrection({ ...correction,
                                                                    unite: e.target.value })} />
                            <label htmlFor="correction-note">Motif</label>
                            <input id="correction-note" value={correction.note}
                                   onChange={(e) => setCorrection({ ...correction,
                                                                    note: e.target.value })} />
                            <div className="rangee-boutons">
                              <button type="button" id="correction-enregistrer"
                                      disabled={occupe || !correction.valeur.trim()}
                                      onClick={() => void decider(x, {
                                        decision: "correct",
                                        final_value: {
                                          value: valeurSaisie(correction.valeur),
                                          unit: correction.unite.trim() || null,
                                        },
                                        note: correction.note.trim() || null,
                                      })}>
                                Enregistrer la correction
                              </button>
                              <button type="button" className="secondaire"
                                      onClick={() => setCorrection(null)}>
                                Annuler
                              </button>
                            </div>
                          </div>
                        )}

                        {rejet?.id === x.extraction_id && (
                          <div className="formulaire-decision">
                            <label htmlFor="rejet-note">Motif du rejet</label>
                            <input id="rejet-note" value={rejet.note}
                                   onChange={(e) => setRejet({ ...rejet, note: e.target.value })} />
                            <div className="rangee-boutons">
                              <button type="button" id="rejet-enregistrer" disabled={occupe}
                                      onClick={() => void decider(x, {
                                        decision: "reject", note: rejet.note.trim() || null })}>
                                Rejeter définitivement
                              </button>
                              <button type="button" className="secondaire"
                                      onClick={() => setRejet(null)}>
                                Annuler
                              </button>
                            </div>
                          </div>
                        )}

                        {(x.status === "confirmed" || x.status === "corrected")
                          && x.form_field && (
                          <div className="rangee-boutons">
                            <button type="button" className="secondaire"
                                    id={`reporter-${x.extraction_id}`}
                                    onClick={() => void reporterUne(x)}
                                    title={`Renseigne « ${x.form_field_label} » dans l'étude`}>
                              Reporter dans l&apos;étude
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {!visibles.length && (
            <p className="aide" id="revue-vide">Aucune valeur pour ces filtres.</p>
          )}
        </>
      )}
    </section>
  );
}
