#!/usr/bin/env python3
"""Rendre aux fiches belges l'empreinte COMPLETE de leur document source.

CE QUE CE SCRIPT REPARE
------------------------
Vingt-deux parametres de `be.json` portaient, en `source_doc_id`, une chaine
de 48 caracteres hexadecimaux. Ce n'est pas un SHA-256 — il en fait 64. La
constante du generateur, dans `record_be_ec2_reading.py`, etait tronquee et
son commentaire affirmait le contraire; elle portait meme une concatenation
suivie d'un commentaire annoncant un remplacement a l'execution qui n'a jamais
eu lieu.

Ce que la troncature coutait: `passerelle._ecart_de_sujet` exige que le
dossier signe cite la MEME empreinte que le registre. Elle le faisait donc sur
192 bits au lieu de 256, et surtout le registre nommait un document qu'aucun
depot ne pouvait rendre — la valeur ne correspondait a l'empreinte d'aucun
fichier.

CE QU'IL NE FAIT PAS: RECALCULER
---------------------------------
Le PDF n'est pas dans le depot et n'y sera pas: NBN EN 1992-1-1 ANB est un
document payant et non redistribuable. L'empreinte est donc **restauree depuis
les references enregistrees**, et deux sources independantes du depot la
portent, identiques:

  * `tools/ndp_import/src/ndp_import/data/catalogue.json`, entree
    `BE-EN199211-NA`, champ `doc_id_sha256`;
  * `docs/relecture/dossier_be_EN199211.md`, ligne « Empreinte SHA-256 », pour
    le fichier `aea3d1fd-506913780NBNEN199211ANB2010F.pdf`.

Ce script LIT ces deux sources, refuse si elles divergent, et refuse si la
valeur restauree n'est pas le prolongement exact de celle que le registre
portait. C'est ce qui rend la restauration verifiable sans le fichier: une
empreinte qui ne prolonge pas la precedente designerait un AUTRE document.

CE QU'IL NE TOUCHE PAS
-----------------------
* `w_max` — il porte l'empreinte d'un AUTRE exemplaire, celui sur lequel le
  Tableau 7.1N-ANB a ete lu. Deux exemplaires de la meme edition, deux rendus,
  deux empreintes: les confondre effacerait le fait que le tableau n'etait
  lisible que sur le second.
* Les six fiches sans `source_doc_id` — `alpha_cw`, `nu1_coeff`,
  `nu1_fck_divisor`, `rho_w_min_coeff`, `s_l_max_coeff`, `s_t_max_coeff`.
  Elles sont `deprecated`, remplacees par les regles typees de
  `ndp/rules_be_ec2.py`, et leur absence d'empreinte est le fait qu'aucune
  lecture ne les porte plus.
* Tout parametre d'un autre pays.
* Tout parametre `confirmed` — il n'y en a aucun, et s'il y en avait un, une
  confirmation porte sur un contenu: la deplacer sous un contenu modifie est
  precisement ce que le chemin d'autorite interdit.

LES ATTESTATIONS ANTERIEURES NE SUIVENT PAS
--------------------------------------------
Aucune confirmation enregistree ne se reporte sur les fiches modifiees, et ce
n'est pas ce script qui s'en charge: `passerelle._ecart_de_sujet` compare
l'empreinte du dossier signe a celle du registre et refuse tout ecart. Une
attestation prise sur l'empreinte tronquee reste dans l'historique — elle a eu
lieu — et n'ouvre plus rien. C'est le comportement voulu.

Lancer depuis tools/ndp_import/ :
    python scripts/restore_be_doc_digest.py [--dry-run]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DATASET = REPO / "engine/src/eurostruct_engine/ndp/data/be.json"
CATALOGUE = REPO / "tools/ndp_import/src/ndp_import/data/catalogue.json"
DOSSIER = REPO / "docs/relecture/dossier_be_EN199211.md"

DOC_KEY = "BE-EN199211-NA"

#: Ce que le registre portait. 48 caracteres: les 192 premiers bits.
TRONQUE = "7951964092a4ad595f4d7ea95bea7e2099ca75d83c669a05"

#: L'empreinte de l'exemplaire sur lequel le Tableau 7.1N-ANB a ete lu. Ce
#: script ne doit pas y toucher — voir le docstring.
W_MAX_DOC = "3a19536221aef69b16435b88bc05d7aee05cebe823e98cb292e49e48fe68dcdd"

_SHA256 = re.compile(r"\b([0-9a-f]{64})\b")


def depuis_le_catalogue() -> str:
    data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    for doc in data["documents"]:
        if doc.get("doc_key") == DOC_KEY:
            return str(doc.get("doc_id_sha256") or "")
    raise SystemExit(f"REFUS: aucune entree {DOC_KEY} dans {CATALOGUE.name}.")


def depuis_le_dossier() -> str:
    for ligne in DOSSIER.read_text(encoding="utf-8").splitlines():
        if "Empreinte SHA-256" in ligne:
            trouve = _SHA256.search(ligne)
            if trouve:
                return trouve.group(1)
    raise SystemExit(
        f"REFUS: aucune ligne « Empreinte SHA-256 » lisible dans "
        f"{DOSSIER.name}.")


def main(argv: list[str]) -> int:
    from ndp_import.review import dataset_indent

    catalogue = depuis_le_catalogue()
    dossier = depuis_le_dossier()

    # DEUX SOURCES, ET ELLES DOIVENT DIRE LA MEME CHOSE. Une seule source
    # serait une declaration; deux qui concordent sont un recoupement.
    if catalogue != dossier:
        print(f"REFUS: le catalogue porte {catalogue[:16]}… et le dossier de "
              f"relecture {dossier[:16]}…. Les deux references du meme "
              "fichier divergent: il faut trancher a la main, pas ici.",
              file=sys.stderr)
        return 2
    complet = catalogue

    if len(complet) != 64:
        print(f"REFUS: l'empreinte enregistree fait {len(complet)} caracteres, "
              "pas 64.", file=sys.stderr)
        return 2
    if not complet.startswith(TRONQUE):
        print(f"REFUS: {complet[:16]}… ne prolonge pas l'identifiant que le "
              f"registre portait ({TRONQUE[:16]}…). Ce serait un AUTRE "
              "document, et la substitution romprait la liaison documentaire "
              "au lieu de la reparer.", file=sys.stderr)
        return 2

    brut = DATASET.read_text(encoding="utf-8")
    data = json.loads(brut)

    touches: list[str] = []
    preserves: list[tuple[str, str]] = []
    for annexe in data["annexes"]:
        for nom, fiche in annexe["parameters"].items():
            actuel = fiche.get("source_doc_id")
            if actuel == TRONQUE:
                if fiche.get("validation_status") == "confirmed":
                    print(f"REFUS: {nom} est CONFIRME. Deplacer une fiche "
                          "confirmee sous une autre empreinte reporterait une "
                          "attestation sur un contenu modifie.",
                          file=sys.stderr)
                    return 2
                fiche["source_doc_id"] = complet
                touches.append(nom)
            elif actuel is None:
                preserves.append((nom, "sans empreinte — fiche obsolete"))
            elif actuel == W_MAX_DOC:
                preserves.append((nom, "autre exemplaire (Tableau 7.1N-ANB)"))
            else:
                preserves.append((nom, f"empreinte inattendue {actuel[:16]}…"))

    if not argv or "--dry-run" not in argv:
        DATASET.write_text(
            json.dumps(data, indent=dataset_indent(brut), ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )

    print(f"Empreinte restauree depuis {CATALOGUE.name} et {DOSSIER.name},")
    print("NON RECALCULEE — l'exemplaire NBN n'est pas versionne.")
    print()
    print(f"  avant  {TRONQUE}   ({len(TRONQUE)} car.)")
    print(f"  apres  {complet}   ({len(complet)} car.)")
    print(f"  ajoute {complet[len(TRONQUE):]}")
    print()
    print(f"{len(touches)} fiche(s) rattachee(s) a l'empreinte complete:")
    print("  " + ", ".join(sorted(touches)))
    print()
    print(f"{len(preserves)} fiche(s) laissee(s) telle(s) quelle(s):")
    for nom, pourquoi in sorted(preserves):
        print(f"  {nom:26s} {pourquoi}")
    print()
    print("AUCUN statut n'a change. Les attestations anterieures restent dans")
    print("l'historique et n'ouvrent plus rien: la passerelle compare")
    print("l'empreinte du dossier signe a celle du registre et refuse l'ecart.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
