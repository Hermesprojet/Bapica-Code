"use client";

/**
 * Le modèle structurel d'un DXF, DESSINÉ tel que le serveur l'a lu.
 *
 * CE QUE LA PERSONNE VOIT
 * ------------------------
 * La grille et ses étiquettes, les poteaux, les voiles, les poutres avec leurs
 * travées (repère et entre-axes), les dalles — et ce qui n'a pas pu être
 * résolu, avec sa raison. Une ligne de la revue désigne son élément sur le
 * dessin, et un élément du dessin désigne ses lignes dans la revue.
 *
 * CE QUE L'ÉCRAN NE FAIT PAS
 * ---------------------------
 * Il ne mesure rien et ne reconnaît rien : chaque trait vient du modèle
 * enregistré avec l'analyse. Les longueurs sont dans l'unité du dessin, et une
 * travée y est une distance entre appuis, jamais la portée utile.
 */
import { useEffect, useMemo, useState } from "react";
import type { Projet } from "@/lib/atelier";
import {
  lireStructure,
  type DocumentDepose, type ModeleStructurel as Modele, type StructureDuDocument,
} from "@/lib/documents";
import { AppelRefuse, type PorteurDeJeton } from "@/lib/transport";
import { enClair } from "@/lib/messages";

type Pt = number[];

function enPhrase(cause: unknown): string {
  return cause instanceof AppelRefuse ? cause.detail : enClair(cause);
}

/** Le plan en coordonnées d'écran : y vers le bas, donc retourné. */
const vers = (p: Pt): [number, number] => [p[0], -p[1]];
const chemin = (points: Pt[]) => points.map((p) => vers(p).join(",")).join(" ");

function bande(axe: Pt[], largeur: number | null | undefined): Pt[] | null {
  if (!largeur || axe.length < 2) return null;
  const [a, b] = axe;
  const l = Math.hypot(b[0] - a[0], b[1] - a[1]);
  if (!l) return null;
  const n = [-(b[1] - a[1]) / l * largeur / 2, (b[0] - a[0]) / l * largeur / 2];
  return [[a[0] + n[0], a[1] + n[1]], [b[0] + n[0], b[1] + n[1]],
          [b[0] - n[0], b[1] - n[1]], [a[0] - n[0], a[1] - n[1]]];
}

function emprise(m: Modele): [number, number, number, number] | null {
  const xs: number[] = [];
  const ys: number[] = [];
  const ajouter = (points: Pt[]) => points.forEach((p) => { xs.push(p[0]); ys.push(p[1]); });
  m.grid.forEach((a) => ajouter(a.line));
  m.columns.forEach((c) => ajouter(c.outline));
  (m.piles ?? []).forEach((p) => ajouter([p.centre]));
  m.walls.forEach((w) => ajouter(w.outline));
  m.beams.forEach((b) => ajouter(b.axis));
  m.slabs.forEach((s) => ajouter(s.outline));
  if (!xs.length) return null;
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

const nombre = (v: number | null | undefined) =>
  v === null || v === undefined ? "—" : String(v).replace(".", ",");

export function ModeleStructurel({ projet, porteur, document, selection, surSelection }: {
  projet: Projet; porteur: PorteurDeJeton; document: DocumentDepose;
  //: Les éléments que la revue désigne (une travée et sa poutre, un poteau…).
  selection: ReadonlySet<string>;
  surSelection: (ids: string[]) => void;
}) {
  //: `undefined` PENDANT LE CHARGEMENT, `null` QUAND IL N'Y A PAS DE MODELE.
  const [lu, setLu] = useState<StructureDuDocument | null | undefined>(undefined);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    let vivant = true;
    lireStructure(porteur, projet.project_id, document.document_id)
      .then((s) => { if (vivant) setLu(s); })
      .catch((cause) => { if (vivant) { setLu(null); setErreur(enPhrase(cause)); } });
    return () => { vivant = false; };
  }, [porteur, projet.project_id, document.document_id]);

  const m = lu?.structure ?? null;
  const cadre = useMemo(() => (m ? emprise(m) : null), [m]);

  if (lu === undefined) {
    return <p className="aide" id="modele-chargement" role="status">
      Chargement du modèle structurel…</p>;
  }
  if (!m) {
    return erreur
      ? <p className="bandeau refus" role="alert">{erreur}</p>
      : null;
  }
  const unite = m.units.drawing ? ` ${m.units.drawing}` : "";
  const c = m.counts;
  const choisi = (...ids: string[]) => ids.some((id) => selection.has(id));
  const classe = (base: string, ...ids: string[]) => base + (choisi(...ids) ? " choisi" : "");

  let figure = null;
  if (cadre) {
    const [x0, y0, x1, y1] = cadre;
    const taille = Math.max(x1 - x0, y1 - y0) || 1;
    const marge = taille * 0.08;
    const em = taille / 55;
    const vue = `${x0 - marge} ${-y1 - marge} ${x1 - x0 + 2 * marge} ${y1 - y0 + 2 * marge}`;
    figure = (
      <svg className="plan-modele" id="modele-plan" viewBox={vue}
           role="img" preserveAspectRatio="xMidYMid meet"
           aria-label={`Modèle lu sur le dessin : ${c.columns} poteau(x), ${c.beams} `
             + `poutre(s), ${c.spans} travée(s), ${c.slabs} dalle(s)`}>
        {m.slabs.map((s) => (
          <polygon key={s.id} className={classe("plan-dalle", s.id)}
                   points={chemin(s.outline)}>
            <title>{`Dalle ${s.mark ?? s.id} : ${nombre(s.lx)} × ${nombre(s.ly)}${unite}`}</title>
          </polygon>
        ))}
        {m.grid.map((a) => {
          const [p, q] = a.line;
          const [tx, ty] = vers(q);
          return (
            <g key={a.id} className={classe("plan-axe", a.id)}>
              <line x1={vers(p)[0]} y1={vers(p)[1]} x2={tx} y2={ty} />
              <text x={tx} y={ty} dy={-em * 0.4} fontSize={em * 1.3}
                    textAnchor="middle">{a.label ?? a.name}</text>
            </g>
          );
        })}
        {m.walls.map((w) => (
          <polygon key={w.id} className={classe("plan-voile", w.id)}
                   points={chemin(w.outline)}
                   onClick={() => surSelection([w.id])}>
            <title>{`Voile ${w.mark ?? w.id} : épaisseur ${nombre(w.thickness)}${unite}`}</title>
          </polygon>
        ))}
        {m.beams.map((b) => {
          const forme = bande(b.axis, b.width);
          return forme
            ? <polygon key={b.id} className={classe("plan-poutre", b.id)}
                       points={chemin(forme)} onClick={() => surSelection([b.id])}>
                <title>{`Poutre ${b.marks.join("/") || b.id} : largeur ${nombre(b.width)}${unite}`}</title>
              </polygon>
            : <polyline key={b.id} className={classe("plan-poutre", b.id)}
                        points={chemin(b.axis)} onClick={() => surSelection([b.id])} />;
        })}
        {m.spans.map((t) => {
          const [a, b] = t.line.map(vers);
          const milieu = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
          const verticale = Math.abs(b[0] - a[0]) < Math.abs(b[1] - a[1]);
          return (
            <g key={t.id} className={classe("plan-travee", t.id)}
               onClick={() => surSelection([t.id, t.beam])}>
              <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} />
              <text x={milieu[0]} y={milieu[1]} dy={-em * 0.5} fontSize={em}
                    textAnchor="middle"
                    transform={verticale ? `rotate(-90 ${milieu[0]} ${milieu[1]})` : undefined}>
                {`${t.mark ?? t.id} · ${nombre(t.axis_length)}`}
              </text>
            </g>
          );
        })}
        {/* LES PIEUX: montrés et comptés, jamais des poteaux; rien n'en est
            proposé. */}
        {(m.piles ?? []).map((p) => {
          const [cx, cy] = vers(p.centre);
          return p.shape === "cercle" && p.diameter
            ? <circle key={p.id} className="plan-pieu" cx={cx} cy={cy} r={p.diameter / 2}>
                <title>{`Pieu ${p.mark ?? p.id} : Ø ${nombre(p.diameter)}${unite}`}</title>
              </circle>
            : p.outline
              ? <polygon key={p.id} className="plan-pieu" points={chemin(p.outline)}>
                  <title>{`Pieu ${p.mark ?? p.id}`}</title>
                </polygon>
              : null;
        })}
        {/* LES POTEAUX PAR-DESSUS: un appui se voit, et se choisit, au-dessus
            des travées qu'il porte. */}
        {m.columns.map((p) => (
          <polygon key={p.id} className={classe("plan-poteau", p.id)}
                   points={chemin(p.outline)} onClick={() => surSelection([p.id])}>
            <title>{`Poteau ${p.mark ?? ""} ${p.grid_node ?? ""} : `
              + `${nombre(p.width ?? p.diameter)} × ${nombre(p.depth ?? p.diameter)}${unite}`}</title>
          </polygon>
        ))}
      </svg>
    );
  }

  return (
    <div className="modele" id="modele-structurel" data-document={document.document_id}>
      <h4>Modèle structurel lu sur le dessin</h4>
      <p className="aide" id="modele-resume">
        {c.grid_axes} axe(s), {c.columns} poteau(x)
        {c.piles ? `, ${c.piles} pieu(x) (montrés, rien n'en est proposé)` : ""},
        {" "}{c.walls} voile(s), {c.beams}{" "}
        poutre(s), {c.spans} travée(s){c.cantilevers ? `, ${c.cantilevers} console(s)` : ""},
        {" "}{c.slabs} dalle(s) — longueurs en{" "}
        <strong>{m.units.drawing ?? "unité non déclarée"}</strong>
        {m.units.source === "declaration_et_cotes"
          ? " (mention écrite et cotes du dessin)" : ""}
        {m.units.source === "echelle_ecrite_et_cotes"
          ? " (échelle écrite sur la feuille et cotes concordantes)" : ""}
        {m.units.source === "echelle_de_presentation"
          ? " (échelle écrite dans la présentation et fenêtre du dessin)" : ""}.
        {" "}{lu?.notice}
      </p>
      {figure}
      <div className="defilement">
        <table id="modele-travees">
          <thead>
            <tr><th>Travée</th><th>Appuis</th><th>Entre-axes</th><th>Nu à nu</th>
              <th>Cote du dessin</th><th>Confiance</th></tr>
          </thead>
          <tbody>
            {m.spans.map((t) => (
              <tr key={t.id} id={`modele-${t.id.replace(/[:.]/g, "-")}`}
                  className={choisi(t.id, t.beam) ? "choisi" : undefined}
                  onClick={() => surSelection([t.id, t.beam])}>
                <td>
                  <strong>{t.mark ?? t.id}</strong>
                  <span className="aide">
                    {" "}{t.kind === "cantilever" ? "console" : `travée ${t.index}/${t.count}`}
                  </span>
                </td>
                <td>
                  {t.from?.grid_node ?? t.from?.support ?? "bout libre"}
                  {" → "}
                  {t.to?.grid_node ?? t.to?.support ?? "bout libre"}
                  <span className="aide">
                    {" "}({[t.from?.kind, t.to?.kind].filter(Boolean).join(" / ")})
                  </span>
                </td>
                <td>{nombre(t.axis_length)}{unite}</td>
                <td>{nombre(t.clear_length)}{unite}</td>
                <td>
                  {t.dimensions.length === 0 ? <span className="aide">aucune</span>
                    : t.dimensions.map((d) => (
                      <span key={d.handle}
                            className={`etat ${d.forced_mismatch ? "ko" : "ok"}`}>
                        {d.displayed}{d.forced_mismatch ? " ≠ mesure" : " ✓"}
                      </span>))}
                </td>
                <td>{Math.round(t.confidence * 100)} %</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {m.unresolved.length > 0 && (
        <div className="bandeau alerte" id="modele-non-resolus" role="status">
          <strong>Non résolu sur ce dessin — rien n&apos;en est proposé</strong>
          <ul>
            {m.unresolved.map((n) => (
              <li key={n.element}><code>{n.element}</code> : {n.reason}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
