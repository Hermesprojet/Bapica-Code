#!/usr/bin/env python3
"""Declare the §7.2 and §7.3 national parameters the SLS module needs.

Two different acts, kept apart on purpose
-----------------------------------------
For **Belgium** the values below were read in NBN EN 1992-1-1 ANB:2010 (F),
pages 17-18, and each carries its page and the sentence it was read in. Two of
them are genuine national deviations, not repetitions of the EN recommendation:

* §7.2(2) ``k1_stress_limit`` — the annex applies the compressive-stress limit
  to *every* exposure class (0,6) and tightens it to 0,5 for XD, XF and XS.
  EN 1992-1-1 only imposes it for XD/XF/XS. A single scalar cannot hold this:
  it is stored as a conditional parameter.
* §7.3.1(5) ``w_max`` — the annex REPLACES Table 7.1N with Table 7.1N-ANB.

That second one is where this script had to be careful, and it no longer owns
the answer. The annex says the table changes; the OCR of the table's numeric
cells was not legible on the copy this script was written against, so the
values it writes for ``w_max`` are the ones from Table 7.1N of EN 1992-1-1,
and its note says so in as many words.

**Since 2026-09-13, ``record_be_ec2_wmax_reading.py`` owns the Belgian
``w_max`` fiche** and overwrites what this script leaves there: Table
7.1N-ANB was read by eye on another copy (folio 18, PDF page 20), and the
fiche now carries a transcription of the Belgian table with provenance
``national_annex``. Run that script after this one for Belgium. Both leave
``validation_status = pending_verification`` — transcribing is not
confirming.

For **France, Spain and Germany** no annex has been opened for §7.2 or §7.3.
The values are the EN recommendations, declared as placeholders so the module
has something to refuse in strict mode, with ``en_recommended`` recording where
they come from.

Nothing here reaches ``confirmed``. Strict mode goes on blocking, in all four
countries, and that is the intended outcome.

Run from tools/ndp_import/:
    python scripts/declare_sls_parameters.py [--dry-run]
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "engine/src/eurostruct_engine/ndp/data"

BE_DOC_REF = "NBN EN 1992-1-1 ANB"
BE_EDITION = "1e ed., aout 2010"

#: Conditions for w_max, following the rows of Table 7.1N. The vocabulary is
#: declared here and matched exactly by the calculation module; an annex that
#: sliced the exposure classes differently would make the module fail loudly
#: instead of silently picking a neighbouring row.
W_MAX_X0_XC1 = "X0_XC1"
W_MAX_XC2_XC4_XD_XS = "XC2_XC4_XD_XS"

#: Conditions for k1 of §7.2(2), following the Belgian split.
K1_XD_XF_XS = "XD_XF_XS"
K1_OTHER = "other"

#: Conditions for K of Table 7.4N — the structural system. A single scalar
#: would be wrong by a factor of nearly four between a cantilever (0,4) and an
#: interior span (1,5), and nothing in the geometry announces which is which.
K_SYSTEMS: list[tuple[str, float, str]] = [
    ("simply_supported", 1.0,
     "Tab. 7.4N: poutre isostatique, dalle isostatique portant dans une ou "
     "deux directions."),
    ("end_span_continuous", 1.3,
     "Tab. 7.4N: travee de rive d'une poutre continue ou d'une dalle continue "
     "portant dans une direction, ou dalle portant dans deux directions "
     "continue le long d'un grand cote."),
    ("interior_span_continuous", 1.5,
     "Tab. 7.4N: travee intermediaire d'une poutre ou d'une dalle portant "
     "dans une ou deux directions."),
    ("flat_slab", 1.2,
     "Tab. 7.4N: dalle sur appuis ponctuels (plancher-dalle), sur la base de "
     "la plus grande portee."),
    ("cantilever", 0.4, "Tab. 7.4N: console."),
]


def _en(
    value: float | None,
    unit: str,
    clause: str,
    description: str,
    *,
    en_recommended: float | None = None,
    variants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """A parameter nobody has read yet: the EN recommendation, as a placeholder."""
    entry: dict[str, Any] = {
        "parameter_value": value,
        "unit": unit,
        "clause": clause,
        "description": description,
        "en_recommended": en_recommended if en_recommended is not None else value,
        "source_type": "en_recommended",
        "validation_status": "pending_verification",
        "verified_at": None,
        "verified_by": None,
        "notes": (
            "VALEUR RECOMMANDEE PAR L'EN, utilisee comme valeur d'attente. "
            "L'Annexe Nationale de ce pays N'A PAS ETE OUVERTE pour cette clause. "
            "Ce qui manque: le texte publie de l'AN pour "
            f"{clause}. Le mode strict refuse de calculer tant que la valeur "
            "n'a pas ete relevee et confirmee par un ingenieur."
        ),
    }
    if variants is not None:
        entry["variants"] = variants
        entry["parameter_value"] = None
    # ECRITE, PAS DEDUITE, ET EN DERNIER — comme dans les fichiers.
    #
    # `NationalParameter.__post_init__` sait la deriver de `source_type`, mais
    # son propre commentaire dit que la derivation est une cale de migration
    # et non un service: une fiche qui signifie « valeur d'attente » doit le
    # declarer elle-meme. Le champ manquait ici, si bien que rejouer ce script
    # RETIRAIT du jeu une provenance que le fichier portait deja.
    #
    # La POSITION compte aussi: `json.dumps` ecrit les cles dans l'ordre du
    # dictionnaire. La placer ailleurs qu'a la fin reordonnerait chaque fiche
    # touchee, pour un contenu identique — encore un diff illisible.
    entry["value_provenance"] = "eurocode_default"
    return entry


def _be(
    value: float | None,
    unit: str,
    clause: str,
    description: str,
    page: int,
    wording: str,
    *,
    en_recommended: float | None = None,
    variants: list[dict[str, Any]] | None = None,
    doc_id: str | None = None,
) -> dict[str, Any]:
    """A parameter read in the Belgian annex, with its page. Still unconfirmed."""
    entry: dict[str, Any] = {
        "parameter_value": value,
        "unit": unit,
        "clause": clause,
        "description": description,
        "en_recommended": en_recommended,
        "source_type": "national_annex",
        "validation_status": "pending_verification",
        "verified_at": None,
        "verified_by": None,
        "source_page": page,
        "notes": (
            f"LU dans {BE_DOC_REF} ({BE_EDITION}), p. {page}. NON CONFIRME par "
            f"un ingenieur: le mode strict continue de bloquer. Texte releve — "
            f"{wording}"
        ),
    }
    if doc_id:
        entry["source_doc_id"] = doc_id
    if variants is not None:
        entry["variants"] = variants
        entry["parameter_value"] = None
    return entry


# ---------------------------------------------------------------------------
# Belgium — transcribed, page by page
# ---------------------------------------------------------------------------
def be_parameters(doc_id: str | None) -> dict[str, dict[str, Any]]:
    return {
        "k1_stress_limit": _be(
            None, "dimensionless", "§7.2(2)",
            "Coefficient limitant la contrainte de compression du beton sous "
            "combinaison caracteristique, pour eviter la fissuration "
            "longitudinale: sigma_c <= k1 f_ck",
            17,
            "§7.2(2): « k1 = 0,6 pour toutes les classes d'exposition sauf XD, "
            "XF et XS pour lesquelles k1 = 0,5. » ECART: l'EN ne prescrit la "
            "limitation que pour XD, XF et XS, avec k1 = 0,6. L'ANB l'etend a "
            "toutes les classes ET la resserre a 0,5 pour XD, XF, XS.",
            en_recommended=0.6, doc_id=doc_id,
            variants=[
                {
                    "condition": K1_XD_XF_XS, "value": 0.5,
                    "description": "§7.2(2) ANB: classes XD, XF et XS — k1 = 0,5.",
                },
                {
                    "condition": K1_OTHER, "value": 0.6,
                    "description": (
                        "§7.2(2) ANB: « k1 = 0,6 pour toutes les classes "
                        "d'exposition sauf XD, XF et XS »."
                    ),
                },
            ],
        ),
        "k3_steel_stress": _be(
            0.8, "dimensionless", "§7.2(5)",
            "Coefficient limitant la contrainte de traction de l'acier sous "
            "combinaison caracteristique: sigma_s <= k3 f_yk",
            17,
            "§7.2(5): « Les valeurs recommandees de k3 (0,8), k4 (1,0) et k5 "
            "(0,75) sont normatives. »",
            en_recommended=0.8, doc_id=doc_id,
        ),
        "k4_steel_stress_imposed": _be(
            1.0, "dimensionless", "§7.2(5)",
            "Coefficient applicable a la contrainte de l'acier lorsqu'elle "
            "resulte d'une deformation imposee: sigma_s <= k4 f_yk",
            17,
            "§7.2(5): « Les valeurs recommandees de k3 (0,8), k4 (1,0) et k5 "
            "(0,75) sont normatives. »",
            en_recommended=1.0, doc_id=doc_id,
        ),
        "w_max": _be(
            None, "mm", "§7.3.1(5), Tab. 7.1N",
            "Ouverture de fissure maximale admissible, elements en beton arme, "
            "sous combinaison quasi-permanente des charges",
            17,
            "§7.3.1(5): « Le tableau 7.1N devient (ajout de la mention des "
            "classes d'environnement associees aux classes d'exposition) » "
            "Tableau 7.1N-ANB. ATTENTION — LES VALEURS PORTEES ICI SONT CELLES "
            "DU TABLEAU 7.1N DE L'EN, PAS CELLES DU TABLEAU 7.1N-ANB. Les "
            "cellules numeriques du tableau belge ne sont pas lisibles sur "
            "l'exemplaire depouille (seule la valeur 0,3 de la ligne XD est "
            "partiellement lisible). CE QUI MANQUE: une lecture des cellules du "
            "Tableau 7.1N-ANB, p. 17, et la correspondance classe d'exposition "
            "/ classe d'environnement NBN B 15-001 que l'ANB y ajoute.",
            en_recommended=0.3, doc_id=doc_id,
            variants=[
                {
                    "condition": W_MAX_X0_XC1, "value": 0.4,
                    "description": (
                        "Tab. 7.1N de l'EN, ligne X0/XC1 — 0,4 mm. NON RELEVE "
                        "dans le Tableau 7.1N-ANB."
                    ),
                },
                {
                    "condition": W_MAX_XC2_XC4_XD_XS, "value": 0.3,
                    "description": (
                        "Tab. 7.1N de l'EN, lignes XC2-XC4 et XD1-XD3/XS1-XS3 — "
                        "0,3 mm. La valeur 0,3 est partiellement lisible sur la "
                        "ligne XD du Tableau 7.1N-ANB."
                    ),
                },
            ],
        ),
        "k3_crack_spacing": _be(
            3.4, "dimensionless", "§7.3.4(3), eq. (7.11)",
            "Coefficient k3 de l'espacement maximal des fissures s_r,max",
            17,
            "§7.3.4(3): « Les valeurs recommandees de k3 (3,4) et k4 (0,425) "
            "sont normatives. »",
            en_recommended=3.4, doc_id=doc_id,
        ),
        "k4_crack_spacing": _be(
            0.425, "dimensionless", "§7.3.4(3), eq. (7.11)",
            "Coefficient k4 de l'espacement maximal des fissures s_r,max",
            17,
            "§7.3.4(3): « Les valeurs recommandees de k3 (3,4) et k4 (0,425) "
            "sont normatives. »",
            en_recommended=0.425, doc_id=doc_id,
        ),
        "K_span_depth": _be(
            None, "dimensionless", "§7.4.2(2), Tab. 7.4N",
            "Coefficient K du rapport portee/hauteur utile dispensant du "
            "calcul de la fleche, selon le systeme structural",
            18,
            "§7.4.2(2): « Les valeurs de K recommandees (Tableau 7.4N) sont "
            "normatives. » A RAPPROCHER de §7.4.1(3), ou l'ANB ajoute: « La "
            "norme NBN B 03-003 donne des indications quant aux limites de "
            "fleches en fonction de la destination de l'element. » CE "
            "DOCUMENT N'EST PAS EN MAIN: les limites de fleche belges (§7.4.1) "
            "restent inconnues. Seule la dispense du §7.4.2 est modelisee.",
            doc_id=doc_id,
            variants=[
                {"condition": cond, "value": value, "description": desc}
                for cond, value, desc in K_SYSTEMS
            ],
        ),
    }


# ---------------------------------------------------------------------------
# France, Spain, Germany — EN recommendations, declared as placeholders
# ---------------------------------------------------------------------------
def en_parameters() -> dict[str, dict[str, Any]]:
    return {
        "k1_stress_limit": _en(
            0.6, "dimensionless", "§7.2(2)",
            "Coefficient limitant la contrainte de compression du beton sous "
            "combinaison caracteristique: sigma_c <= k1 f_ck",
            variants=[
                {
                    "condition": K1_XD_XF_XS, "value": 0.6,
                    "description": (
                        "§7.2(2): l'EN impose la limitation pour les classes "
                        "XD, XF et XS, avec k1 = 0,6 recommande."
                    ),
                },
                {
                    "condition": K1_OTHER, "value": 0.6,
                    "description": (
                        "§7.2(2): hors XD/XF/XS l'EN n'impose pas la "
                        "limitation. La valeur 0,6 est reconduite faute "
                        "d'Annexe Nationale relevee — A VERIFIER: l'AN de ce "
                        "pays peut, comme l'ANB belge, etendre ou lever la "
                        "limitation dans ces classes."
                    ),
                },
            ],
        ),
        "k3_steel_stress": _en(
            0.8, "dimensionless", "§7.2(5)",
            "Coefficient limitant la contrainte de traction de l'acier sous "
            "combinaison caracteristique: sigma_s <= k3 f_yk",
        ),
        "k4_steel_stress_imposed": _en(
            1.0, "dimensionless", "§7.2(5)",
            "Coefficient applicable a la contrainte de l'acier resultant d'une "
            "deformation imposee: sigma_s <= k4 f_yk",
        ),
        "w_max": _en(
            None, "mm", "§7.3.1(5), Tab. 7.1N",
            "Ouverture de fissure maximale admissible, elements en beton arme, "
            "sous combinaison quasi-permanente des charges",
            en_recommended=0.3,
            variants=[
                {
                    "condition": W_MAX_X0_XC1, "value": 0.4,
                    "description": "Tab. 7.1N de l'EN, ligne X0/XC1 — 0,4 mm.",
                },
                {
                    "condition": W_MAX_XC2_XC4_XD_XS, "value": 0.3,
                    "description": (
                        "Tab. 7.1N de l'EN, lignes XC2-XC4 et "
                        "XD1-XD3/XS1-XS3 — 0,3 mm."
                    ),
                },
            ],
        ),
        "k3_crack_spacing": _en(
            3.4, "dimensionless", "§7.3.4(3), eq. (7.11)",
            "Coefficient k3 de l'espacement maximal des fissures s_r,max",
        ),
        "k4_crack_spacing": _en(
            0.425, "dimensionless", "§7.3.4(3), eq. (7.11)",
            "Coefficient k4 de l'espacement maximal des fissures s_r,max",
        ),
        "K_span_depth": _en(
            None, "dimensionless", "§7.4.2(2), Tab. 7.4N",
            "Coefficient K du rapport portee/hauteur utile dispensant du "
            "calcul de la fleche, selon le systeme structural",
            variants=[
                {"condition": cond, "value": value, "description": desc}
                for cond, value, desc in K_SYSTEMS
            ],
        ),
    }


def _annex(data: dict[str, Any]) -> dict[str, Any]:
    return next(
        a for a in data["annexes"]
        if a["standard_family"] == "EN 1992" and a["part"] == "1-1"
    )


#: Provenances qui signifient QU'UN HUMAIN A OUVERT L'ANNEXE. Une fiche qui en
#: porte une n'est plus une place a tenir, et ce script n'a rien a y ecrire.
_DEJA_LU = {"national_annex", "national_annex_pending", "composed_normative_rule"}


def _pourquoi_ne_pas_ecraser(existant: Mapping[str, Any]) -> str | None:
    """Ce script POSE DES VALEURS D'ATTENTE. Il n'ecrase pas une lecture.

    CE QU'IL A DETRUIT, ET COMMENT. Rejoue apres
    ``record_fr_ec2_reading.py``, il remettait les sept fiches ELS francaises
    a la recommandation EN: `w_max` reperdait sa citation du Tableau 7.1NF,
    son folio 16 et son empreinte de document, et `k3_crack_spacing`
    reperdait son statut ``not_representable`` — c'est-a-dire le fait que
    l'annexe francaise y met une FORMULE en fonction de l'enrobage, que le
    modele scalaire ne sait pas porter. Le mode strict se serait rouvert sur
    une valeur que la France ne retient pas.

    Aucune erreur ne s'affichait: le script disait « FR: 7 parametres » et
    repartait. L'ordre des scripts etait la seule chose qui protegeait les
    lectures, et un ordre n'est pas une garantie.

    Trois etats sont donc preserves, et chacun dit pourquoi:
    """
    if existant.get("validation_status") == "confirmed":
        return "deja CONFIRME"
    if existant.get("validation_status") == "not_representable":
        # L'annexe y met une expression que le modele scalaire ne porte pas.
        # Reposer une valeur d'attente rouvrirait un calcul que ce statut
        # ferme volontairement.
        return "NON REPRESENTABLE — l'annexe y met une expression"
    provenance = existant.get("value_provenance")
    if provenance in _DEJA_LU:
        return f"deja relevee dans l'annexe (provenance « {provenance} »)"
    return None




def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    written: list[str] = []

    for code in ("be", "fr", "es", "de"):
        path = DATA / f"{code}.json"
        # L'INDENTATION EN PLACE, PAS UNE INDENTATION IMPOSEE. `be.json` et
        # `fr.json` sont a une espace, `de.json` et `es.json` a deux. Ecrire
        # `indent=2` partout reindentait 515 lignes pour la Belgique et 852
        # pour l'Espagne, et sept fiches transcrites disparaissaient dedans.
        from ndp_import.review import dataset_indent

        brut = path.read_text(encoding="utf-8")
        creux = dataset_indent(brut)
        data = json.loads(brut)
        annex = _annex(data)

        if code == "be":
            # Reuse the digest already recorded for this annex rather than
            # re-deriving it: the file it names is the one that was read.
            doc_id = annex["parameters"].get("alpha_cc", {}).get("source_doc_id")
            new = be_parameters(doc_id)
        else:
            new = en_parameters()

        poses = 0
        for name, entry in new.items():
            existing = annex["parameters"].get(name) or {}
            raison = _pourquoi_ne_pas_ecraser(existing)
            if raison:
                print(f"  {code}: {name} — non ecrase ({raison})")
                continue
            annex["parameters"][name] = entry
            poses += 1

        if not dry:
            path.write_text(
                json.dumps(data, indent=creux, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        # LE COMPTE EST CELUI DES FICHES REELLEMENT ECRITES. Annoncer
        # « 7 parametres » alors que sept ont ete preserves laisserait croire
        # qu'un jeu a ete repose, et c'est exactement l'inverse.
        written.append(
            f"{code.upper()}: {poses} pose(s), {len(new) - poses} preserve(s)")

    print("Parametres ELS §7.2 / §7.3 declares")
    for line in written:
        print("  " + line)
    print()
    print("BE: transcrits de NBN EN 1992-1-1 ANB p. 17-18, sauf w_max dont les")
    print("    cellules du Tableau 7.1N-ANB n'etaient pas lisibles sur")
    print("    l'exemplaire depouille ici — les valeurs portees sont celles du")
    print("    Tableau 7.1N de l'EN, et la note le dit.")
    print("    -> LANCER ENSUITE scripts/record_be_ec2_wmax_reading.py, qui")
    print("       remplace cette fiche par la lecture visuelle du tableau")
    print("       belge (folio 18, page PDF 20). Sans lui, w_max reste une")
    print("       valeur d'attente et le quatre-yeux refusera de la confirmer.")
    print("FR/ES/DE: valeurs recommandees EN, aucune Annexe Nationale ouverte.")
    print()
    print("AUCUN parametre n'est passe en 'confirmed'. Le mode strict refuse")
    print("toujours de calculer, dans les quatre pays.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
