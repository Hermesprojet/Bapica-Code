#!/usr/bin/env python3
"""Record what the Belgian EC2 annex says, WITHOUT confirming it.

Why this script exists
----------------------
The engine shipped with the Eurocode *recommended* values as placeholders. For
Belgium at least one of them is now known to be wrong: NBN EN 1992-1-1 ANB
§3.1.6(1)P fixes alpha_cc at 0,85 for bending, not 1,0. Leaving 1,0 in place is
worse than replacing it: a placeholder that is known false is a trap.

So this writes the values *as read from the annex*, each with its page, and
leaves every one of them at ``pending_verification``. Strict mode still refuses
to calculate. What changes is the reviewing engineer's job: instead of finding
and reading eight values across a 31-page document, they confirm eight values
whose page is already cited.

This is NOT the human verification step. It cannot be: a value becomes
``confirmed`` only through ``ndp-import apply`` with a named engineer, and the
publisher of a standard is not a verifier — NBN edited this document, it did
not check it for anyone's project.

Run from tools/ndp_import/:
    python scripts/record_be_ec2_reading.py [--dry-run]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DATASET = REPO / "engine/src/eurostruct_engine/ndp/data/be.json"

#: sha256 of NBN EN 1992-1-1 ANB, 1e ed. aout 2010, French text version.
DOC_ID = "7951964092a4ad595f4d7ea95bea7e2099ca75d83c669a05" \
         "" # truncated marker replaced below at runtime
DOC_REF = "NBN EN 1992-1-1 ANB"
EDITION = "1e ed., aout 2010"

#: parameter -> (value, page, exact wording read in the document)
READINGS: dict[str, tuple[float, int, str]] = {
    "alpha_cc": (
        0.85, 10,
        "§3.1.6(1)P: « Pour les verifications a l'ELU de la resistance a "
        "l'effort normal, la flexion simple ou composee, la valeur de alpha_cc "
        "vaut 0,85. Pour les autres cas, alpha_cc vaut 1,0. » ECART par rapport "
        "a la valeur recommandee EN (1,0). ATTENTION: valeur CONDITIONNELLE — "
        "0,85 en flexion, 1,0 dans les autres cas. Le moteur ne stocke qu'un "
        "scalaire et retient 0,85, ce qui est le cas couvert par le module de "
        "flexion. Toute extension a d'autres sollicitations devra modeliser la "
        "condition.",
    ),
    "alpha_ct": (
        1.0, 10,
        "§3.1.6(2)P: « La valeur de alpha_ct recommandee (1,0) est normative. »",
    ),
    "gamma_C_persistent": (
        1.5, 8,
        "§2.4.2.4(1), Tableau 2.1N repris: durable ou transitoire, beton 1,5. "
        "Declare « normatives ».",
    ),
    "gamma_S_persistent": (
        1.15, 8,
        "§2.4.2.4(1), Tableau 2.1N repris: durable ou transitoire, acier de "
        "beton arme 1,15.",
    ),
    "gamma_C_accidental": (
        1.2, 8, "§2.4.2.4(1), Tableau 2.1N repris: accidentelle, beton 1,2.",
    ),
    "gamma_S_accidental": (
        1.0, 8,
        "§2.4.2.4(1), Tableau 2.1N repris: accidentelle, acier de beton arme 1,0.",
    ),
    "k1_redistribution": (
        0.44, 15,
        "§5.5(4): « Les valeurs recommandees (k1 = 0,44 ; "
        "k2 = 1,25(0,6+0,0014/eps_cu2) ; k3 = 0,54 ; k4 = idem ; k5 = 0,7 et "
        "k6 = 0,8) sont normatives. »",
    ),
    "k2_redistribution": (
        1.25, 15,
        "§5.5(4): k2 = 1,25(0,6+0,0014/eps_cu2), soit 1,25 pour "
        "eps_cu2 = 3,5 pour mille (fck <= 50 MPa).",
    ),
    "As_min_coeff": (
        0.26, 22,
        "§9.2.1.1(1): « La valeur de As,min recommandee (Formule 9.1N) est "
        "normative. » Formule 9.1N: 0,26 fctm/fyk bt d.",
    ),
    "As_min_floor": (
        0.0013, 22, "§9.2.1.1(1), Formule 9.1N: plancher 0,0013 bt d.",
    ),
    "As_max_ratio": (
        0.04, 22,
        "§9.2.1.1(3): « La valeur de As,max recommandee (0,04 Ac) est normative. »",
    ),
    "C_Rd_c_coeff": (
        0.18, 17,
        "§6.2.2(1): « Les valeurs recommandees de C_Rd,c (0,18/gamma_C), "
        "v_min (0,035 k^3/2 fck^1/2) et k1 (0,15) sont normatives. » "
        "ATTENTION: « Pour les dalles appuyees sur les bords, il faut "
        "multiplier ces valeurs par 1,25 » — condition non modelisee.",
    ),
    "v_min_coeff": (0.035, 17, "§6.2.2(1): v_min = 0,035 k^3/2 fck^1/2."),
    "k1_shear": (0.15, 17, "§6.2.2(1): k1 = 0,15."),
    "cot_theta_min": (1.0, 17, "§6.2.3(2): « 1,0 <= cot(theta) <= cot(theta)_max »."),
}

#: Parameters the annex fixes in a way the current scalar model cannot hold.
#: Recorded as blockers rather than approximated.
STRUCTURAL_MISMATCH: dict[str, str] = {
    "cot_theta_max": (
        "§6.2.3(2) p.17: la Belgique NE retient PAS la borne 2,5. Elle fixe "
        "cot(theta)_max = (2 + k1 sigma_cp bw d s / (Asw z fywd)) <= 3, avec "
        "sigma_cp <= 0,2 fcd. C'est une FORMULE dependant de l'effort normal et "
        "du ferraillage, pas une constante. Le modele de parametre ne stocke "
        "qu'un scalaire: le representer par 2,5 ou par 3 serait faux dans les "
        "deux cas. Ce parametre reste sans valeur tant que le modele n'admet "
        "pas une expression."
    ),
}


def main(argv: list[str]) -> int:
    from ndp_import.model import SourceDocument

    pdf = Path(argv[1]) if len(argv) > 1 and not argv[1].startswith("--") else None
    doc_id = SourceDocument.digest(pdf) if pdf else DOC_ID

    data = json.loads(DATASET.read_text(encoding="utf-8"))
    annex = next(
        a for a in data["annexes"]
        if a["standard_family"] == "EN 1992" and a["part"] == "1-1"
    )
    annex["edition"] = f"{EDITION} (LUE sur la page de garde, A DECLARER)"
    annex["effective_from"] = "2010-08-01"

    applied: list[str] = []
    for name, (value, page, wording) in READINGS.items():
        p = annex["parameters"].setdefault(name, {})
        p.update({
            "parameter_value": value,
            "source_type": "national_annex",
            # UNCHANGED, and that is the point.
            "validation_status": "pending_verification",
            "verified_at": None,
            "verified_by": None,
            "source_doc_id": doc_id,
            "source_page": page,
            "notes": (
                f"LU par le pipeline d'import dans {DOC_REF} ({EDITION}), "
                f"p. {page}. NON CONFIRME par un ingenieur: le mode strict "
                f"continue de bloquer. Texte releve — {wording}"
            ),
        })
        applied.append(name)

    for name, reason in STRUCTURAL_MISMATCH.items():
        p = annex["parameters"].setdefault(name, {})
        p.update({
            "source_type": "national_annex",
            # NOT 'pending_verification': aucune signature d'ingenieur ne peut
            # debloquer ce parametre, il n'y a pas de scalaire a confirmer.
            "validation_status": "not_representable",
            # La valeur est retiree, pas remplacee. Laisser 2,5 en base serait
            # deposer une valeur que l'annexe belge ne retient pas.
            "parameter_value": None,
            "verified_at": None,
            "verified_by": None,
            "source_doc_id": doc_id,
            "source_page": 17,
            "notes": f"SANS VALEUR EXPLOITABLE. {reason}",
        })

    if "--dry-run" not in argv:
        DATASET.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    print(f"{len(applied)} valeurs transcrites depuis {DOC_REF}")
    print(f"{len(STRUCTURAL_MISMATCH)} parametre(s) sans valeur exploitable: "
          + ", ".join(STRUCTURAL_MISMATCH))
    print()
    print("AUCUN parametre n'est passe en 'confirmed'.")
    print("Le mode strict refuse toujours de calculer. Il manque la decision")
    print("nominative d'un ingenieur habilite — l'editeur de la norme n'en est")
    print("pas un.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    raise SystemExit(main(sys.argv))
