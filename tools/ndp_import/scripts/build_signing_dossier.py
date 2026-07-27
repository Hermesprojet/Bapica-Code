#!/usr/bin/env python3
"""Build the dossier a named engineer signs, and measure the extractor.

Why both in one script
----------------------
The signature is not a formality, and the dossier has to prove it. So this
puts the machine's proposal and the hand reading side by side for every
parameter, and counts how often the machine was right.

That count is the argument for the human gate. If the extractor agreed with
the hand reading everywhere, someone would eventually ask why a person is
still in the loop. It does not agree — and the dossier says so, per line, in
front of the engineer who is about to put their name on it.

Outputs
-------
* ``dossier_<country>_<standard>.md`` — what the engineer reads and works from.
* ``decisions_<country>_<standard>.json`` — the file they fill in, pre-loaded
  with candidate ids, clauses and pages. Every ``verified_by`` is left EMPTY
  on purpose: this script must never be able to produce a signature.

Run from tools/ndp_import/:
    python scripts/build_signing_dossier.py --run RUN.json --country BE \
        --standard "EN 1992-1-1" --out-dir DIR
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]


def _hand_readings(country: str, standard: str) -> dict[str, dict[str, Any]]:
    """What was transcribed by hand, from the engine dataset."""
    path = REPO / f"engine/src/eurostruct_engine/ndp/data/{country.lower()}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    family, _, part = standard.rpartition("-")
    family = family.rsplit("-", 1)[0] if family.count("-") else family
    for annex in data["annexes"]:
        if f"{annex['standard_family']}-{annex['part']}" == standard:
            return annex["parameters"]
    return {}


def _verdict(machine: float | None, hand: Any, hand_page: int | None) -> str:
    """Compare, but only where a comparison means something.

    A parameter still carrying the EN recommendation has no ``source_page``:
    nobody has opened the annex at it. Scoring the extractor against that
    placeholder would count a disagreement with a value we never read as an
    extractor error — inflating the denominator with cases that cannot be
    judged either way. Those come back NON JUGEABLE and stay out of the rate.
    """
    if hand_page is None:
        return "NON JUGEABLE"
    if hand is None:
        return "SANS VALEUR"
    if machine is None:
        return "RIEN LU"
    return "concorde" if abs(machine - float(hand)) < 1e-9 else "DIVERGE"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--country", required=True)
    ap.add_argument("--standard", required=True, help='ex. "EN 1992-1-1"')
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args(argv[1:])

    run = json.loads(args.run.read_text(encoding="utf-8"))
    doc = run["document"]
    hand = _hand_readings(args.country, args.standard)

    best: dict[str, dict[str, Any]] = {}
    for c in run["candidates"]:
        cur = best.get(c["parameter_name"])
        if cur is None or c["confidence"] > cur["confidence"]:
            best[c["parameter_name"]] = c

    names = sorted(set(hand) | set(best))
    rows, decisions = [], []
    agree = diverge = nothing = novalue = unjudgeable = 0

    for name in names:
        h = hand.get(name, {})
        b = best.get(name)
        hv = h.get("parameter_value")
        mv = b["parsed_value"] if b else None
        v = _verdict(mv, hv, h.get("source_page"))
        agree += v == "concorde"
        diverge += v == "DIVERGE"
        nothing += v == "RIEN LU"
        novalue += v == "SANS VALEUR"
        unjudgeable += v == "NON JUGEABLE"

        rows.append({
            "name": name,
            "machine": mv, "machine_page": b["page"] if b else None,
            "confidence": b["confidence"] if b else None,
            "hand": hv, "hand_page": h.get("source_page"),
            "clause": h.get("clause") or (b.get("clause") if b else None),
            "verdict": v,
            "status": h.get("validation_status", "absent du jeu de donnees"),
        })
        if b is not None:
            decisions.append({
                "candidate_id": b["candidate_id"],
                "parameter_name": name,
                "_clause": h.get("clause"),
                "_page_lue_a_la_main": h.get("source_page"),
                "_valeur_proposee_par_la_machine": mv,
                "_valeur_lue_a_la_main": hv,
                # A REMPLIR PAR L'INGENIEUR. Vides, et le resteront: ce script
                # n'a pas le droit de produire une signature.
                "outcome": "",
                "final_value": None,
                "verified_by": "",
                "verified_at": "",
                "source_page": h.get("source_page"),
                "notes": "",
            })

    args.out_dir.mkdir(parents=True, exist_ok=True)
    slug = f"{args.country.lower()}_{args.standard.replace(' ', '').replace('-', '')}"

    dec_path = args.out_dir / f"decisions_{slug}.json"
    dec_path.write_text(
        json.dumps(decisions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    total = len(rows)
    judged = agree + diverge + nothing          # comparaisons qui ont un sens
    md = [
        f"# Dossier de relecture — {doc['reference']} ({doc['edition']})",
        "",
        f"- Fichier : `{doc['filename']}`, {doc['page_count']} pages",
        f"- Empreinte SHA-256 : `{doc['doc_id']}`",
        f"- Déposé par : {doc['deposited_by']}",
        f"- Extraction : {run['extractor_version']}, le {run['run_at']}",
        "",
        "## Ce que vous signez",
        "",
        "En renseignant `verified_by`, vous attestez avoir **ouvert ce document",
        "à la page citée** et y avoir lu la valeur que vous inscrivez. Vous",
        "n'attestez pas que la machine a bien lu : elle se trompe souvent, et",
        "le tableau ci-dessous le mesure.",
        "",
        "## Fiabilité mesurée de l'extraction automatique",
        "",
        "Mesurée uniquement sur les paramètres qu'un humain a déjà ouverts dans",
        "ce document. Ceux qui portent encore la valeur recommandée par l'EN",
        "sont **non jugeables** : personne n'a lu l'annexe à leur sujet, et les",
        "compter fausserait le taux dans un sens comme dans l'autre.",
        "",
        "| Verdict | Nombre | Part du jugeable |",
        "|---|---:|---:|",
        f"| Concorde avec la lecture humaine | {agree} | {agree/judged:.0%} |",
        f"| **Diverge** | {diverge} | {diverge/judged:.0%} |",
        f"| Rien lu | {nothing} | {nothing/judged:.0%} |",
        f"| **Total jugeable** | **{judged}** | |",
        f"| Sans valeur exploitable (hors taux) | {novalue} | — |",
        f"| Non jugeable, valeur EN par défaut (hors taux) | {unjudgeable} | — |",
        f"| **Total paramètres** | **{total}** | |",
        "",
        f"> La machine propose la bonne valeur dans **{agree} cas sur {judged}**",
        f"> jugeables. Elle se trompe {diverge} fois. C'est la raison d'être de",
        "> votre signature : aucune de ces propositions n'entre dans le moteur",
        "> sans elle.",
        "",
        "## Paramètre par paramètre",
        "",
        "| Paramètre | Clause | Machine | p. | Conf. | Lecture main | p. | Verdict |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        md.append(
            f"| `{r['name']}` | {r['clause'] or '—'} | "
            f"{r['machine'] if r['machine'] is not None else '—'} | "
            f"{r['machine_page'] or '—'} | "
            f"{r['confidence'] if r['confidence'] is not None else '—'} | "
            f"{r['hand'] if r['hand'] is not None else '—'} | "
            f"{r['hand_page'] or '—'} | {r['verdict']} |"
        )
    md += [
        "",
        "## Marche à suivre",
        "",
        f"1. Ouvrir `{dec_path.name}`.",
        "2. Pour chaque entrée : ouvrir le document à la page citée, lire la",
        "   valeur, puis renseigner `outcome` (`accepted` / `corrected` /",
        "   `rejected` / `deferred`), `final_value`, `verified_by` (**nom de",
        "   personne**, pas un organisme) et `verified_at` (ISO 8601).",
        "3. Appliquer :",
        "",
        "```",
        f"ndp-import apply --run {args.run.name} --decisions {dec_path.name} \\",
        f"    --dataset engine/src/eurostruct_engine/ndp/data/{args.country.lower()}.json",
        "```",
        "",
        "Toute décision sans nom de vérificateur, sans horodatage, sans page ou",
        "sans source officielle est refusée par `to_engine_records`.",
    ]
    doss_path = args.out_dir / f"dossier_{slug}.md"
    doss_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"dossier   : {doss_path}")
    print(f"decisions : {dec_path}  ({len(decisions)} entrees, verified_by VIDE)")
    print()
    print(f"Fiabilite de l'extraction sur le JUGEABLE: {agree}/{judged} "
          f"concordances, {diverge} divergences, {nothing} sans lecture.")
    print(f"Hors taux: {novalue} sans valeur exploitable, {unjudgeable} non "
          f"jugeable(s) — valeur EN par defaut, jamais ouverte dans l'annexe.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(HERE / "src"))
    raise SystemExit(main(sys.argv))
