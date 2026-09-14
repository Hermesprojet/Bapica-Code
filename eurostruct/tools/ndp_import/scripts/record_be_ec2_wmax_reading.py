#!/usr/bin/env python3
"""Transcrire le Tableau 7.1N-ANB, sans le confirmer et sans deposer le PDF.

POURQUOI CE SCRIPT EXISTE A COTE DE `record_be_ec2_reading.py`
---------------------------------------------------------------
`record_be_ec2_reading.py` a transcrit ce que le pipeline d'import savait lire
de la NBN EN 1992-1-1 ANB. Il n'a jamais su lire le Tableau 7.1N-ANB: sur
l'exemplaire depouille a l'epoque, les cellules du tableau ne rendaient rien.
La fiche `w_max` est donc restee des mois avec les nombres du Tableau 7.1N de
l'EUROCODE, etiquetes `national_annex_pending` pour que personne ne les prenne
pour des valeurs belges.

Le tableau a ete lu, a l'oeil, sur un autre exemplaire — celui dont l'empreinte
est ``DOC_ID`` ci-dessous, le meme que celui deja cite par
``ndp/rules_be_ec2.py`` pour les six regles typees belges. Ce script porte
cette lecture, et rien d'autre.

CE QU'IL NE FAIT PAS, ET C'EST LE POINT
----------------------------------------
* **Il ne depose pas le PDF.** NBN EN 1992-1-1 ANB est un document payant et
  non redistribuable. Le depot ne contient pas l'exemplaire et ne le contiendra
  pas. Passer ``--pdf CHEMIN`` fait VERIFIER que le fichier pointe porte bien
  l'empreinte declaree, et refuse sinon; sans ``--pdf``, l'empreinte declaree
  est ecrite telle quelle et la fiche dit qu'elle vient d'une lecture visuelle.
* **Il ne confirme rien.** ``validation_status`` reste
  ``pending_verification``. Transcrire n'est pas confirmer: la confirmation est
  l'acte date de deux ingenieurs nommes, enregistre par le chemin d'autorite.
  Un script du depot ne peut pas la produire, et celui-ci refuse de l'ecrire.
* **Il n'extrapole pas.** Le tableau n'a pas de ligne pour XF ni pour XA. Ce
  script n'en invente pas: `ExposureClass.w_max_condition` refuse ces classes
  faute de classe associee declaree.

Lancer depuis tools/ndp_import/ :
    python scripts/record_be_ec2_wmax_reading.py [--pdf CHEMIN] [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DATASET = REPO / "engine/src/eurostruct_engine/ndp/data/be.json"

#: sha256 COMPLET (64 caracteres) de l'exemplaire sur lequel le tableau a ete
#: lu. Le meme que `_ANB_DOC` dans `ndp/rules_be_ec2.py`.
DOC_ID = "3a19536221aef69b16435b88bc05d7aee05cebe823e98cb292e49e48fe68dcdd"
DOC_REF = "NBN EN 1992-1-1 ANB:2010 (F)"
EDITION = "1re edition, aout 2010"

#: Pour l'ANB, folio = page PDF - 2 (deux pages de couverture). Les deux sont
#: portees: le folio est ce qu'un ingenieur cite, la page PDF ce qu'un script
#: ouvre, et les confondre a deja produit une reference fausse dans ce jeu.
FOLIO = 18
PAGE_PDF = 20

CLAUSE = "§7.3.1(5), Tab. 7.1N-ANB"

#: Les quatre lignes du tableau, colonne « beton arme, combinaison
#: quasi-permanente ». Ecrites ligne par ligne comme le tableau les imprime;
#: le regroupement en deux variantes vient apres, et il est explicite.
LIGNES: tuple[tuple[str, float], ...] = (
    ("X0, XC1", 0.4),
    ("XC2, XC3, XC4", 0.3),
    ("XD1, XD2, XD3", 0.3),
    ("XS1, XS2, XS3", 0.3),
)

#: Les variantes telles que le registre les porte. Le vocabulaire des
#: conditions est celui que `ExposureClass.w_max_condition` produit.
VARIANTES = [
    {
        "condition": "X0_XC1",
        "value": 0.4,
        "description": (
            "Tableau 7.1N-ANB, ligne X0/XC1, colonne beton arme sous "
            "combinaison quasi-permanente — cellule imprimee « 0,4^1 », soit "
            "0,4 mm; l'exposant est un appel de note."
        ),
    },
    {
        "condition": "XC2_XC4_XD_XS",
        "value": 0.3,
        "description": (
            "Tableau 7.1N-ANB, lignes XC2/XC3/XC4, XD1/XD2/XD3 et "
            "XS1/XS2/XS3, colonne beton arme sous combinaison "
            "quasi-permanente — 0,3 mm sur les trois lignes, sans appel de "
            "note."
        ),
    },
]

NOTES = (
    "TRANSCRIT du Tableau 7.1N-ANB de NBN EN 1992-1-1 ANB:2010 (F), "
    "1re edition, aout 2010, §7.3.1(5), folio 18 = page PDF 20 (pour l'ANB, "
    "folio = pdf - 2). Lecture visuelle des cellules du tableau belge, "
    f"exemplaire d'empreinte SHA-256 {DOC_ID} — l'exemplaire depouille "
    "auparavant par le pipeline d'import ne rendait pas ces cellules. "
    "LES QUATRE LIGNES RELEVEES, colonne « beton arme, combinaison "
    "quasi-permanente »: X0/XC1 = 0,4 mm; XC2/XC3/XC4 = 0,3 mm; "
    "XD1/XD2/XD3 = 0,3 mm; XS1/XS2/XS3 = 0,3 mm. LES EXPOSANTS DU TABLEAU "
    "SONT DES APPELS DE NOTES, PAS DES CHIFFRES: la cellule imprimee "
    "« 0,4^1 » vaut 0,4 et non 0,41, la cellule imprimee « 0,2^2 » vaut 0,2 "
    "et non 0,22. La cellule « 0,2^2 » n'appartient pas a la colonne "
    "transcrite ici et n'est donc pas portee: ce module ne couvre pas la "
    "precontrainte. CE QUI RESTE HORS DE CETTE FICHE: le tableau ne donne "
    "aucune ligne pour XF ni pour XA, et la correspondance classe "
    "d'exposition / classe d'environnement NBN B 15-001 que l'ANB ajoute au "
    "tableau n'est pas modelisee — `ExposureClass` refuse XF et XA sans "
    "classe associee plutot que de les rabattre sur 0,3. NON CONFIRME par un "
    "ingenieur: le mode strict continue de bloquer, et seul le chemin "
    "d'autorite a quatre yeux peut lever ce statut."
)


def _empreinte(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for bloc in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path, default=None,
                    help="exemplaire a verifier. JAMAIS versionne: document "
                         "NBN payant et non redistribuable.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv[1:])

    if args.pdf is not None:
        # UNE EMPREINTE QU'ON TAPE EST UNE EMPREINTE QU'ON PEUT INVENTER.
        # Quand le fichier est la, on la recalcule et on refuse tout ecart.
        reelle = _empreinte(args.pdf)
        if reelle != DOC_ID:
            print(f"REFUS: {args.pdf.name} porte l'empreinte {reelle[:16]}…, "
                  f"la lecture a ete faite sur {DOC_ID[:16]}…. Ce n'est pas "
                  "le meme fichier, et la transcription ne s'y rattache pas.",
                  file=sys.stderr)
            return 2
        print(f"empreinte verifiee sur {args.pdf.name}: {DOC_ID[:16]}…")
    else:
        print("PDF absent — normal: l'exemplaire NBN n'est pas versionne.")
        print(f"empreinte DECLAREE, non verifiee ici: {DOC_ID[:16]}…")

    brut = DATASET.read_text(encoding="utf-8")
    data = json.loads(brut)
    annexe = next(
        a for a in data["annexes"]
        if a["standard_family"] == "EN 1992" and a["part"] == "1-1"
    )
    fiche = annexe["parameters"]["w_max"]

    if fiche.get("validation_status") == "confirmed":
        print("REFUS: la fiche porte deja 'confirmed'. Ce script transcrit; "
              "il ne confirme pas, et il n'ecrase pas une confirmation.",
              file=sys.stderr)
        return 2

    fiche.update({
        # AUCUNE VALEUR UNIQUE: elle servirait de defaut a l'appelant qui
        # oublie de dire dans quelle classe il se trouve.
        "parameter_value": None,
        "unit": "mm",
        "clause": CLAUSE,
        "source_type": "national_annex",
        # INCHANGE, ET C'EST LE POINT.
        "validation_status": "pending_verification",
        "verified_at": None,
        "verified_by": None,
        "source_doc_id": DOC_ID,
        "source_page": FOLIO,
        "notes": NOTES,
        "variants": VARIANTES,
        # LA PROVENANCE CHANGE, ELLE. Les nombres ne viennent plus du
        # Tableau 7.1N de l'EN mais du Tableau 7.1N-ANB.
        "value_provenance": "national_annex",
    })

    if not args.dry_run:
        # L'INDENTATION EN PLACE. Reindenter reecrirait les 515 lignes du jeu
        # belge pour une fiche modifiee: la revue ne verrait plus ce qui a
        # change, et c'est la revue qui compte ici.
        from ndp_import.review import dataset_indent

        DATASET.write_text(
            json.dumps(data, indent=dataset_indent(brut), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    print()
    print(f"{DOC_REF}, {EDITION}")
    print(f"  {CLAUSE} — folio {FOLIO}, page PDF {PAGE_PDF}")
    for classes, valeur in LIGNES:
        print(f"    {classes:<16s} w_max = {valeur:g} mm")
    print()
    print("Les exposants du tableau sont des appels de notes: « 0,4^1 » vaut")
    print("0,4 et non 0,41. Aucune ligne pour XF ni pour XA — le moteur les")
    print("refuse sans classe associee declaree.")
    print()
    print("AUCUN parametre n'est passe en 'confirmed'. Le mode strict refuse")
    print("toujours de calculer sur ce referentiel. Ce qui a change: la")
    print("valeur est desormais RELEVEE dans l'annexe, donc le chemin")
    print("d'autorite a quatre yeux peut la confirmer — ce qu'il refusait de")
    print("faire sur une valeur d'attente.")
    print()
    print("Penser a regenerer le seed: python db/seed/generate_ndp_seed.py "
          "> db/seed/0001_ndp.sql")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
