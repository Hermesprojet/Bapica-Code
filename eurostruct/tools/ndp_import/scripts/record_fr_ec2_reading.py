#!/usr/bin/env python3
"""Record what NF EN 1992-1-1/NA says, WITHOUT confirming it.

The French concrete annex, mars 2007, indice de classement P18-711-1/NA,
delivered through Reef4. This is the P0 document: every French concrete
parameter the engine holds today was an EN recommendation nobody had checked.

Three of them turn out to be wrong
-----------------------------------
``v_min_coeff`` is the serious one. The engine holds 0,035 — the EN
recommendation. **France does not use it.** §6.2.2(1) replaces the single
expression with four, by element type:

    0,34/gamma_C f_ck^1/2          dalles beneficiant d'un effet de
                                   redistribution transversale
    0,053/gamma_C k^3/2 f_ck^1/2   poutres, et autres dalles
    0,35/gamma_C f_ck^1/2          voiles

For a beam at gamma_C = 1,5 that gives 0,03533, not 0,035 — a 1 % error, small
but real, and in the unsafe direction. For a slab with transverse redistribution
the expression does not even have the same SHAPE: no k^3/2 term at all.

``k3_crack_spacing`` cannot be held as a number. §7.3.4(3) keeps 3,4 only for
covers up to 25 mm; beyond that it becomes ``k3 = 3,4 (25/c)^{2/3}``, c in mm.
At the 40 mm cover of the engine's own reference case that is 2,486 — 27 % from
the stored value. A formula in the cover is not a scalar, so the parameter is
recorded ``not_representable``, like the Belgian ``cot_theta_max``. No signature
unblocks it; the module has to learn the expression first.

``w_max``: §7.3.1(5) sends to **Tableau 7.1NF**, a French table replacing 7.1N.
Its numeric cells do not extract from this rendering — ``extract_tables()``
returns empty rows and the flowing text carries none of the numbers. So the
values stay what they were, and the note says plainly that they are the EN
table's, not France's, and what is missing.

Everything here stays ``pending_verification``. This is not the human
verification step: a value becomes ``confirmed`` only through ``ndp-import
apply`` with a named engineer.

Run from tools/ndp_import/:
    python scripts/record_fr_ec2_reading.py --pdf FILE [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
DATASET = REPO / "engine/src/eurostruct_engine/ndp/data/fr.json"

DOC_REF = "NF EN 1992-1-1/NA"
EDITION = "mars 2007"
INDICE = "P 18-711-1/NA"

#: parameter -> (value, page, wording read in the document)
READINGS: dict[str, tuple[float, int, str]] = {
    "alpha_cc": (
        1.0, 7,
        "§3.1.6(1)P: « La valeur de alpha_cc a utiliser est celle "
        "recommandee. » CONFIRME la valeur 1,0 deja portee. ECART NET avec la "
        "Belgique, dont l'ANB descend a 0,85 en flexion: le meme calcul ne "
        "donne pas le meme resultat dans les deux pays.",
    ),
    "alpha_ct": (
        1.0, 7,
        "§3.1.6(2)P: « La valeur de alpha_ct a utiliser est celle "
        "recommandee. »",
    ),
    "gamma_C_persistent": (
        1.5, 6,
        "§2.4.2.4(1): « Les valeurs des coefficients partiels relatifs aux "
        "materiaux a utiliser pour les etats-limites ultimes sont celles du "
        "Tableau 2.1N recommande. »",
    ),
    "gamma_S_persistent": (
        1.15, 6, "§2.4.2.4(1), Tableau 2.1N recommande: acier 1,15.",
    ),
    "C_Rd_c_coeff": (
        0.18, 12,
        "§6.2.2(1): « Les valeurs a utiliser sont les suivantes: "
        "C_Rd,c = 0,18/gamma_C ». Conforme a la recommandation EN.",
    ),
    "k1_shear": (0.15, 12, "§6.2.2(1): « k1 = 0,15 »."),
    "nu1_coeff": (
        0.6, 12,
        "§6.2.2(6): « La valeur de nu a utiliser est celle recommandee. »",
    ),
    "k4_crack_spacing": (
        0.425, 17,
        "§7.3.4(3): « La valeur de k4 a utiliser est celle recommandee. »",
    ),
}

#: Parameters the annex fixes by CASE. A scalar would be read by whichever
#: module asks first, and be wrong for the others.
CONDITIONAL: dict[str, tuple[float | None, int, str, list[dict]]] = {
    "v_min_coeff": (
        None, 12,
        "§6.2.2(1): la France REMPLACE l'expression unique de l'EN par trois, "
        "selon l'element. ATTENTION — les valeurs stockees ici valent "
        "gamma_C = 1,5 (situation durable ou transitoire). L'annexe ecrit "
        "0,053/gamma_C, pas un nombre: en situation accidentelle "
        "(gamma_C = 1,2) le coefficient devient 0,04417 et non 0,03533. Le "
        "modele ne sait pas porter une expression; ce point reste a traiter.",
        [
            {
                "condition": "beam", "value": 0.053 / 1.5,
                "description": (
                    "§6.2.2(1) NA: « 0,053/gamma_C k^3/2 f_ck^1/2 pour les "
                    "poutres, et pour les dalles autres que celles ci-dessus ». "
                    "0,053/1,5 = 0,035333. La valeur recommandee EN est 0,035: "
                    "proche, et differente."
                ),
            },
            {
                "condition": "slab_with_transverse_redistribution",
                "value": 0.34 / 1.5,
                "description": (
                    "§6.2.2(1) NA: « 0,34/gamma_C f_ck^1/2 sur les dalles "
                    "beneficiant d'un effet de redistribution transversale sous "
                    "le cas de charge considere ». ATTENTION: cette expression "
                    "N'A PAS le terme k^3/2. Un module qui multiplierait cette "
                    "valeur par k^3/2 se tromperait; la condition doit etre "
                    "traitee par le module, pas seulement lue."
                ),
            },
            {
                "condition": "wall", "value": 0.35 / 1.5,
                "description": (
                    "§6.2.2(1) NA: « 0,35/gamma_C f_ck^1/2 pour les voiles ». "
                    "Sans terme k^3/2 non plus."
                ),
            },
        ],
    ),
}

#: Fixed by the annex in a way no scalar can hold.
STRUCTURAL_MISMATCH: dict[str, tuple[int, str]] = {
    "k3_crack_spacing": (
        17,
        "§7.3.4(3) p.17: la France NE retient 3,4 que pour les enrobages "
        "inferieurs ou egaux a 25 mm. « Pour des enrobages plus grands, la "
        "valeur de k3 a utiliser est k3 = 3,4 (25/c)^2/3 (c en mm). » C'est "
        "une FORMULE dependant de l'enrobage, pas une constante. A "
        "l'enrobage de 40 mm du cas de reference du moteur elle vaut 2,486, "
        "soit 27 % sous la valeur stockee — dans le sens qui SOUS-ESTIME "
        "l'espacement des fissures, donc l'ouverture. Ce parametre reste sans "
        "valeur tant que le modele n'admet pas une expression.",
    ),
}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv[1:])

    doc_id = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    annex = next(
        a for a in data["annexes"]
        if a["standard_family"] == "EN 1992" and a["part"] == "1-1"
    )
    annex["reference"] = DOC_REF
    annex["edition"] = f"{EDITION} (LUE en page 1), indice {INDICE}"
    annex["effective_from"] = "2007-03-01"

    def stamp(p: dict, page: int, wording: str) -> None:
        p.update({
            "source_type": "national_annex",
            # INCHANGE, et c'est le but.
            "validation_status": "pending_verification",
            "verified_at": None, "verified_by": None,
            "source_doc_id": doc_id, "source_page": page,
            "notes": (
                f"LU par le pipeline d'import dans {DOC_REF} ({EDITION}), "
                f"p. {page}. NON CONFIRME par un ingenieur: le mode strict "
                f"continue de bloquer. Texte releve — {wording}"
            ),
        })

    for name, (value, page, wording) in READINGS.items():
        p = annex["parameters"].setdefault(name, {})
        p["parameter_value"] = value
        p.pop("variants", None)
        stamp(p, page, wording)

    for name, (_, page, wording, variants) in CONDITIONAL.items():
        p = annex["parameters"].setdefault(name, {})
        p["parameter_value"] = None
        p["variants"] = variants
        stamp(p, page, wording)

    for name, (page, reason) in STRUCTURAL_MISMATCH.items():
        p = annex["parameters"].setdefault(name, {})
        p.update({
            "source_type": "national_annex",
            # PAS 'pending_verification': aucune signature ne debloque une
            # formule que le modele ne sait pas porter.
            "validation_status": "not_representable",
            "parameter_value": None,
            "verified_at": None, "verified_by": None,
            "source_doc_id": doc_id, "source_page": page,
            "notes": f"SANS VALEUR EXPLOITABLE. {reason}",
        })
        p.pop("variants", None)

    # w_max: l'annexe renvoie au Tableau 7.1NF, illisible sur ce rendu.
    w = annex["parameters"].get("w_max")
    if w is not None:
        w["source_doc_id"] = doc_id
        w["source_page"] = 16
        w["source_type"] = "national_annex"
        w["notes"] = (
            "§7.3.1(5) p.15 de " + DOC_REF + f" ({EDITION}): « les valeurs de "
            "w_max a utiliser sont donnees dans le Tableau 7.1NF ». La France "
            "REMPLACE donc le Tableau 7.1N. ATTENTION — LES VALEURS PORTEES "
            "ICI SONT CELLES DU TABLEAU 7.1N DE L'EN, PAS CELLES DU TABLEAU "
            "7.1NF. Les cellules numeriques du tableau francais ne "
            "s'extraient pas de ce rendu (extract_tables rend des lignes "
            "vides, et le texte au fil ne porte aucun des nombres). CE QUI "
            "MANQUE: une lecture des cellules du Tableau 7.1NF, p. 16. "
            "L'annexe ajoute par ailleurs que les dalles et voiles de plus de "
            "0,8 m et les poutres de plus de 2 m relevent de la NF EN 1992-2 "
            "ou 1992-3 — hors du domaine de ce moteur."
        )

    if not args.dry_run:
        DATASET.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    print(f"{DOC_REF} ({EDITION}), indice {INDICE}")
    print(f"empreinte {doc_id[:32]}...")
    print()
    print(f"{len(READINGS)} valeur(s) transcrite(s), inchangees ou confirmees")
    print(f"{len(CONDITIONAL)} parametre(s) rendus CONDITIONNELS:")
    for name, (_, _, _, variants) in CONDITIONAL.items():
        print(f"   {name}: " + ", ".join(
            f"{v['condition']}={v['value']:.5f}" for v in variants))
    print(f"{len(STRUCTURAL_MISMATCH)} parametre(s) SANS VALEUR EXPLOITABLE: "
          + ", ".join(STRUCTURAL_MISMATCH))
    print()
    print("AUCUN parametre n'est passe en 'confirmed'. Le mode strict refuse")
    print("toujours de calculer pour la France.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
