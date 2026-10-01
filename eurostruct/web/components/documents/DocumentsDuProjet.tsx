"use client";

/**
 * L'étape préalable : les pièces du projet, avant la saisie.
 *
 * CE QUE CET ÉCRAN FAIT, ET CE QU'IL NE FAIT PAS
 * ------------------------------------------------
 * Il dépose un fichier (PDF, DXF ; DWG conservé non lu), affiche ce que le
 * serveur en a lu — page par page, avec ce qui n'a pas pu l'être — et ouvre la
 * revue des valeurs proposées. Il ne lit rien lui-même, ne propose rien, ne
 * convertit rien : le format se constate sur les octets côté serveur, et une
 * valeur n'entre dans l'étude qu'après une décision nommée.
 *
 * LA SAISIE MANUELLE RESTE ENTIÈRE. Cet écran est un raccourci, pas un
 * passage obligé : l'étude guidée en dessous fonctionne sans aucun document.
 */
import { useCallback, useEffect, useState } from "react";
import { RevueExtractions } from "./RevueExtractions";
import type { Projet } from "@/lib/atelier";
import {
  EXTENSIONS_ACCEPTEES, NATURES, ROLES_DE_SAISIE, listDocuments, reanalyser,
  telechargerPiece, uploadDocument,
  type ChampPrerempli, type DocumentDepose,
} from "@/lib/documents";
import { AppelRefuse, type PorteurDeJeton } from "@/lib/transport";
import { enClair } from "@/lib/messages";

const CLASSE_STATUT: Record<string, string> = {
  analyse: "ok", partiel: "attente", non_lu: "silence", echec: "ko",
  en_attente: "silence",
};

function enPhrase(cause: unknown): string {
  return cause instanceof AppelRefuse ? cause.detail : enClair(cause);
}

export function DocumentsDuProjet({ projet, porteur, elementCourant, surReport }: {
  projet: Projet | null;
  porteur: PorteurDeJeton;
  //: Le repère de la saisie en cours: la revue préremplit CET élément.
  elementCourant: string;
  surReport: (champs: ChampPrerempli[], resume: string) => void;
}) {
  const [documents, setDocuments] = useState<DocumentDepose[]>([]);
  const [chargement, setChargement] = useState(false);
  const [nature, setNature] = useState(NATURES[0][0]);
  const [fichier, setFichier] = useState<File | null>(null);
  const [depot, setDepot] = useState<string | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; texte: string } | null>(null);
  const [ouvert, setOuvert] = useState<string | null>(null);
  const [survol, setSurvol] = useState(false);

  //: LE DROIT DE DEPOSER SE LIT SUR L'ADHESION; L'ECRAN NE DECIDE DE RIEN.
  //: Il explique un bouton ferme — PostgreSQL rejoue la question et tranche.
  const peutSaisir = !!projet && projet.member_active !== false
    && ROLES_DE_SAISIE.includes(projet.member_role);

  const recharger = useCallback(async () => {
    if (!projet) return;
    setChargement(true);
    try {
      setDocuments(await listDocuments(porteur, projet.project_id));
    } catch (cause) {
      setMessage({ ok: false, texte: enPhrase(cause) });
    } finally {
      setChargement(false);
    }
  }, [projet, porteur]);

  useEffect(() => { void recharger(); }, [recharger]);

  async function deposer() {
    if (!projet || !fichier) return;
    setDepot(fichier.name);
    setMessage(null);
    try {
      const recu = await uploadDocument(porteur, projet.project_id, fichier, nature);
      const d = recu.document;
      setMessage({
        ok: true,
        texte: recu.already_present
          ? `« ${d.filename} » était déjà déposé dans ce projet (mêmes octets) : `
            + "aucune seconde analyse."
          : `« ${d.filename} » déposé — ${d.analysis_status_label.toLowerCase()}`
            + ` : ${recu.extractions_created} valeur(s) proposée(s), aucune `
            + "confirmée. Ouvrez la revue pour décider.",
      });
      setFichier(null);
      await recharger();
      if (recu.extractions_created > 0) setOuvert(d.document_id);
    } catch (cause) {
      setMessage({ ok: false, texte: enPhrase(cause) });
    } finally {
      setDepot(null);
    }
  }

  async function analyserANouveau(d: DocumentDepose) {
    if (!projet) return;
    setMessage(null);
    try {
      const recu = await reanalyser(porteur, projet.project_id, d.document_id);
      setMessage({ ok: true, texte: `« ${d.filename} » analysé à nouveau : `
        + `${recu.document.analysis_status_label.toLowerCase()}, `
        + `${recu.extractions_created} valeur(s) proposée(s).` });
      await recharger();
    } catch (cause) {
      setMessage({ ok: false, texte: enPhrase(cause) });
    }
  }

  const motifDepot = !projet ? "Sélectionnez un projet : une pièce se dépose dans un dossier."
    : !peutSaisir ? `Votre rôle (« ${projet.member_role} »`
      + `${projet.member_active === false ? ", accès révoqué" : ""}) permet de lire `
      + "les pièces, pas d'en déposer."
    : !fichier ? "Choisissez un fichier PDF, DXF ou DWG."
    : null;

  return (
    <section aria-labelledby="titre-documents" id="documents-du-projet">
      <h2 id="titre-documents">Documents du projet — étape préalable</h2>
      <p className="aide">
        Déposez les plans (PDF ou DXF) et le cahier des charges (PDF). Les
        valeurs lues — axes, portées, sections, épaisseurs, niveaux, classes,
        nuances, charges, notes — sont des <strong>propositions</strong> :
        aucune n&apos;entre dans l&apos;étude avant votre décision, et le
        serveur relit cette décision au moment du calcul. Un DXF est lu par sa
        géométrie : grille, poteaux, poutres et leurs appuis donnent les portées
        même quand aucun texte ne les écrit. Un DWG est conservé mais pas lu
        (licence ODA ou RealDWG requise) : exportez-le en DXF.
      </p>

      <fieldset>
        <legend>Déposer une pièce</legend>
        <div className={"depot" + (survol ? " survol" : "")} id="depot-zone"
             onDragOver={(e) => { e.preventDefault(); setSurvol(true); }}
             onDragLeave={() => setSurvol(false)}
             onDrop={(e) => {
               e.preventDefault();
               setSurvol(false);
               const f = e.dataTransfer.files?.[0];
               if (f) setFichier(f);
             }}>
          <div className="grille">
            <div>
              <label htmlFor="depot-nature">Nature</label>
              <select id="depot-nature" value={nature}
                      onChange={(e) => setNature(e.target.value)}>
                {NATURES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="depot-fichier">Fichier (PDF, DXF, DWG — 32 Mio au plus)</label>
              <input id="depot-fichier" type="file" accept={EXTENSIONS_ACCEPTEES}
                     onChange={(e) => setFichier(e.target.files?.[0] ?? null)} />
              <span className="aide">
                {fichier ? `Choisi : ${fichier.name}` : "Ou glissez-le ici."}
              </span>
            </div>
          </div>
          <div className="rangee-boutons">
            <button type="button" id="depot-envoyer"
                    disabled={!!motifDepot || !!depot} onClick={deposer}
                    title={motifDepot ?? "Dépose, puis analyse le document"}>
              {depot ? "Dépôt et analyse en cours…" : "Déposer et analyser"}
            </button>
          </div>
          {motifDepot && fichier !== null && (
            <p className="aide manque" role="status">{motifDepot}</p>
          )}
          {depot && (
            <p className="aide" id="depot-en-cours" role="status">
              « {depot} » : dépôt, relecture de l&apos;empreinte, puis lecture
              (une page sans couche texte passe par l&apos;OCR et prend plus de
              temps).
            </p>
          )}
        </div>
      </fieldset>

      {message && (
        <p className={"bandeau " + (message.ok ? "ok" : "refus")}
           id="documents-message" role={message.ok ? "status" : "alert"}>
          {message.texte}
        </p>
      )}

      {documents.length === 0 ? (
        <p className="aide" id="documents-vide">
          {chargement ? "Chargement des pièces…"
            : "Aucune pièce déposée dans ce projet. La saisie manuelle ci-dessous "
              + "reste entièrement disponible."}
        </p>
      ) : (
        <table id="documents-liste">
          <thead>
            <tr>
              <th>Pièce</th><th>Lecture</th><th>Valeurs</th><th></th>
            </tr>
          </thead>
          <tbody>
            {documents.map((d) => (
              <tr key={d.document_id} id={`document-${d.document_id}`}
                  data-statut={d.analysis_status}>
                <td>
                  <button type="button" className="lien"
                          onClick={() => projet && void telechargerPiece(
                            porteur, projet.project_id, d).catch(
                            (c) => setMessage({ ok: false, texte: enPhrase(c) }))}
                          title="Télécharger les octets déposés">
                    {d.filename}
                  </button>
                  <span className="aide">
                    {" "}{d.kind_label} · {d.format.toUpperCase()}
                    {d.page_count ? ` · ${d.page_count} page(s)` : ""}
                  </span>
                </td>
                <td>
                  <span className={`etat ${CLASSE_STATUT[d.analysis_status] ?? "silence"}`}>
                    {d.analysis_status_label}
                  </span>
                  {d.analysis_detail && (
                    <span className="aide detail-analyse"> {d.analysis_detail}</span>
                  )}
                  {d.structure_summary && (
                    <span className="aide modele-resume" id={`modele-resume-${d.document_id}`}>
                      {" "}Modèle structurel : {d.structure_summary.counts.columns ?? 0} poteau(x),
                      {" "}{d.structure_summary.counts.beams ?? 0} poutre(s),
                      {" "}{d.structure_summary.counts.spans ?? 0} travée(s),
                      {" "}{d.structure_summary.counts.slabs ?? 0} dalle(s)
                      {d.structure_summary.counts.unresolved
                        ? `, ${d.structure_summary.counts.unresolved} non résolu(s)` : ""}
                      {" "}— {d.structure_summary.drawing_units ?? "unité non déclarée"}.
                    </span>
                  )}
                </td>
                <td className="decomptes">
                  {d.proposed_count} à revoir · {d.confirmed_count} confirmée(s)
                  · {d.corrected_count} corrigée(s) · {d.rejected_count} rejetée(s)
                </td>
                <td>
                  <div className="rangee-boutons">
                    {(d.proposed_count + d.confirmed_count + d.corrected_count
                      + d.rejected_count) > 0 && (
                      <button type="button" id={`revoir-${d.document_id}`}
                              className={ouvert === d.document_id ? "" : "secondaire"}
                              onClick={() => setOuvert(
                                ouvert === d.document_id ? null : d.document_id)}>
                        {ouvert === d.document_id ? "Fermer la revue" : "Revoir les valeurs"}
                      </button>
                    )}
                    {d.can_reanalyse && peutSaisir && d.analysis_status !== "en_attente" && (
                      <button type="button" className="secondaire"
                              id={`reanalyser-${d.document_id}`}
                              onClick={() => void analyserANouveau(d)}
                              title="Possible tant qu'aucune valeur n'est proposée">
                        Analyser à nouveau
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {projet && ouvert && (
        <RevueExtractions
          key={ouvert}
          projet={projet} porteur={porteur}
          document={documents.find((d) => d.document_id === ouvert) ?? null}
          peutDecider={peutSaisir}
          elementCourant={elementCourant}
          surDecision={recharger}
          surReport={surReport} />
      )}
    </section>
  );
}
