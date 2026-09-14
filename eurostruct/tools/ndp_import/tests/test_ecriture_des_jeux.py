"""Ce qu'un ecrivain de jeu de donnees n'a pas le droit de faire.

DEUX DEFAUTS MESURES LE 14/09, TOUS DEUX SILENCIEUX
-----------------------------------------------------
1. **Une valeur d'attente ecrasait une lecture.** `declare_sls_parameters.py`
   pose les sept parametres ELS des quatre pays a la recommandation de l'EN,
   « pour que le module ait quelque chose a refuser en mode strict ». Rejoue
   apres `record_fr_ec2_reading.py`, il remettait les sept fiches francaises a
   cette recommandation: `w_max` reperdait sa citation du Tableau 7.1NF, son
   folio et son empreinte de document, et `k3_crack_spacing` reperdait son
   statut `not_representable` — c'est-a-dire le fait que l'annexe francaise y
   met une FORMULE en fonction de l'enrobage. Le script affichait
   « FR: 7 parametres » et repartait. Seul l'ORDRE des scripts protegeait les
   lectures, et un ordre n'est pas une garantie.

2. **Ecrire une fiche reindentait le fichier entier.** `be.json` et `fr.json`
   sont a une espace, `de.json` et `es.json` a deux; tous les ecrivains de
   l'outil imposaient `indent=2`. Importer une poignee de valeurs relues
   produisait un diff de 515 lignes pour la Belgique et 852 pour l'Espagne.
   Un diff qu'on ne peut pas lire est un diff qu'on ne relit pas, et c'est
   justement la relecture qui est le sujet ici.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ndp_import.review import dataset_indent

RACINE = Path(__file__).resolve().parents[3]
SCRIPTS = RACINE / "tools/ndp_import/scripts"
DATA = RACINE / "engine/src/eurostruct_engine/ndp/data"


# ---------------------------------------------------------------------------
# 1. L'indentation en place
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "fichier, attendu",
    [("be.json", 1), ("fr.json", 1), ("de.json", 2), ("es.json", 2)],
)
def test_l_indentation_de_chaque_jeu_est_detectee(fichier: str,
                                                  attendu: int) -> None:
    """Elle est LUE, pas supposee: les quatre fichiers ne sont pas pareils."""
    assert dataset_indent((DATA / fichier).read_text(encoding="utf-8")) == attendu


def test_l_indentation_par_defaut_sert_a_un_fichier_sans_indice() -> None:
    assert dataset_indent("{}\n") == 1
    assert dataset_indent("{}\n", default=4) == 4


# ---------------------------------------------------------------------------
# 2. Une valeur d'attente n'ecrase pas une lecture
# ---------------------------------------------------------------------------
def _pourquoi(existant: dict) -> str | None:
    """Importe la garde depuis le script, qui n'est pas un module installe."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "declare_sls_parameters", SCRIPTS / "declare_sls_parameters.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module._pourquoi_ne_pas_ecraser(existant)


@pytest.mark.parametrize(
    "fiche, motif",
    [
        ({"validation_status": "confirmed"}, "CONFIRME"),
        ({"validation_status": "not_representable"}, "NON REPRESENTABLE"),
        ({"value_provenance": "national_annex"}, "relevee"),
        ({"value_provenance": "national_annex_pending"}, "relevee"),
        ({"value_provenance": "composed_normative_rule"}, "relevee"),
    ],
)
def test_une_fiche_deja_travaillee_est_preservee(fiche: dict,
                                                 motif: str) -> None:
    raison = _pourquoi(fiche)
    assert raison is not None, f"{fiche} aurait ete ecrasee"
    assert motif in raison


@pytest.mark.parametrize(
    "fiche",
    [
        {},
        {"value_provenance": "eurocode_default"},
        {"value_provenance": "eurocode_default",
         "validation_status": "pending_verification"},
    ],
)
def test_une_place_a_tenir_se_laisse_ecraser(fiche: dict) -> None:
    """La garde ne doit pas non plus tout figer: c'est le role du script."""
    assert _pourquoi(fiche) is None


def test_rejouer_le_script_ne_touche_plus_aucun_jeu() -> None:
    """LE CAS DECISIF, ET IL PORTE SUR LES FICHIERS REELS.

    Les quatre jeux sont deja transcrits. Rejouer le declarateur ne doit donc
    rien ecrire du tout — ni valeur, ni indentation. Avant la garde, il
    effacait sept fiches francaises et en reindentait deux fichiers.
    """
    avant = {f.name: f.read_bytes() for f in sorted(DATA.glob("*.json"))}

    acheve = subprocess.run(
        [sys.executable, str(SCRIPTS / "declare_sls_parameters.py")],
        cwd=SCRIPTS.parent, capture_output=True, text=True,
    )
    apres = {f.name: f.read_bytes() for f in sorted(DATA.glob("*.json"))}

    assert acheve.returncode == 0, acheve.stderr
    changes = [n for n in avant if avant[n] != apres[n]]
    assert changes == [], (
        f"rejouer le declarateur a modifie {changes}. Il pose des valeurs "
        "d'attente: sur un jeu deja transcrit, il n'a rien a ecrire."
    )
    # Et il DIT ce qu'il a preserve, au lieu d'annoncer un compte trompeur.
    assert "preserve" in acheve.stdout


def test_le_folio_du_seed_est_un_entier() -> None:
    """`national_annex_parameters.source_page` est une colonne `integer`.

    Le generateur rendait `18.0`. PostgreSQL l'acceptait en arrondissant, donc
    la ligne passait — et le seed affirmait une page fractionnaire.
    """
    seed = (RACINE / "db/seed/0001_ndp.sql").read_text(encoding="utf-8")
    assert ", 18\n" in seed or ", 18\nfrom" in seed
    assert ", 18.0\n" not in seed


def test_le_seed_porte_le_rattachement_documentaire() -> None:
    """La base doit dire ce que les fichiers disent, pas moins.

    La colonne existe depuis la migration 0006 et le generateur ne l'ecrivait
    pas: l'ecran qui lit la base voyait des fiches sans document ni page.
    """
    seed = (RACINE / "db/seed/0001_ndp.sql").read_text(encoding="utf-8")
    assert "source_doc_id, source_page)" in seed

    attendu = json.loads((DATA / "be.json").read_text(encoding="utf-8"))
    empreintes = {
        p["source_doc_id"]
        for a in attendu["annexes"] for p in a["parameters"].values()
        if p.get("source_doc_id")
    }
    for e in empreintes:
        assert f"'{e}'" in seed, f"empreinte {e[:16]}… absente du seed"
