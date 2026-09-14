"""Ce que la commande de démarrage cite doit exister DANS LE DÉPÔT.

CE QUE CES CAS ONT TROUVÉ
-------------------------
`eurostruct/api/.env.example` était cité par le README, par `dev.sh` et par le
rapport de lot. Il existait sur les postes qui l'avaient créé. Il était
**absent de Git** : `.gitignore` portait `.env*`, qui l'avalait au passage.

Un clone neuf recevait donc une instruction — « copiez ce fichier » — désignant
un fichier qui n'y était pas. Et rien ne pouvait s'en apercevoir : tous les
essais partaient d'un arbre où le fichier traînait, non versionné.

POURQUOI ON INTERROGE GIT, ET PAS LE DISQUE
--------------------------------------------
`Path.exists()` aurait répondu « oui » sur la machine où le défaut est né.
C'est exactement ce qui l'a rendu invisible. On demande donc à `git ls-files`,
seule source qui distingue « présent ici » de « présent pour tout le monde ».
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
EUROSTRUCT = RACINE / "eurostruct"


def _suivis() -> set[str]:
    """Les chemins que Git connaît, relatifs à la racine du dépôt."""
    sortie = subprocess.run(
        ["git", "-C", str(RACINE), "ls-files"],
        capture_output=True, text=True, check=True,
    )
    return set(sortie.stdout.splitlines())


#: Ce que le démarrage documenté cite, et qu'un clone neuf doit trouver.
#: Écrit à la main plutôt que découvert: la liste est le contrat, et une
#: découverte automatique se contenterait de constater ce qui existe.
CITES = [
    "eurostruct/api/.env.example",
    "eurostruct/dev.sh",
    "eurostruct/run_tests.sh",
    "eurostruct/web/package.json",
    "eurostruct/api/pyproject.toml",
    "eurostruct/engine/pyproject.toml",
]


@pytest.mark.parametrize("chemin", CITES)
def test_le_demarrage_ne_cite_aucun_fichier_absent_du_depot(chemin: str) -> None:
    suivis = _suivis()
    assert chemin in suivis, (
        f"« {chemin} » est cité par la procédure de démarrage mais n'est pas "
        "suivi par Git. Un clone neuf ne l'aura pas. Vérifiez .gitignore: "
        "c'est « .env* » qui avait avalé le gabarit d'environnement."
    )


def test_le_gabarit_d_environnement_ne_porte_aucune_valeur() -> None:
    """Un gabarit versionné ne doit contenir que des NOMS.

    Deux exceptions assumées et lisibles: le port local de l'API et les
    réglages bornés qui documentent leur propre défaut. Aucune ne peut être un
    secret — et le cas les nomme, pour qu'une troisième ne s'ajoute pas en
    silence.
    """
    gabarit = (EUROSTRUCT / "api" / ".env.example").read_text(encoding="utf-8")
    tolerees = {
        # L'adresse locale de l'API, dans ses deux formes: celle de RUNTIME —
        # lue par le layout a chaque requete, donc jamais figee dans le
        # bundle — et celle de BUILD, repli de commodite pour `npm run dev`.
        "EUROSTRUCT_API_URL": "http://127.0.0.1:8000",
        "NEXT_PUBLIC_EUROSTRUCT_API_URL": "http://127.0.0.1:8000",
        "EUROSTRUCT_JWT_ALGORITHMS": "RS256",
        "EUROSTRUCT_JWT_LEEWAY_S": "60",
    }
    for ligne in gabarit.splitlines():
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        nom, _, valeur = ligne.partition("=")
        if not valeur.strip():
            continue
        assert nom in tolerees and valeur.strip() == tolerees[nom], (
            f"« {ligne} » porte une valeur. Un gabarit versionné ne contient "
            "que des noms: une valeur y devient un secret publié le jour où "
            "quelqu'un renseigne la sienne avant de committer."
        )


def test_le_gabarit_couvre_toutes_les_variables_lues_par_le_code() -> None:
    """Une variable lue mais absente du gabarit est une panne à retardement.

    Elle ne se manifeste qu'au déploiement, sous la forme d'un `/ready` rouge
    dont personne ne sait quelle ligne ajouter.
    """
    gabarit = (EUROSTRUCT / "api" / ".env.example").read_text(encoding="utf-8")
    declarees = set(re.findall(r"^([A-Z_][A-Z0-9_]*)=", gabarit, re.M))

    lues: set[str] = set()
    for dossier in ("api/src", "web/lib", "web/app"):
        for fichier in (EUROSTRUCT / dossier).rglob("*"):
            if fichier.suffix not in {".py", ".ts", ".tsx"}:
                continue
            texte = fichier.read_text(encoding="utf-8", errors="replace")
            # LES BORNES COMPTENT: sans elles, `EUROSTRUCT_API_URL` remonte
            # comme un fragment de `NEXT_PUBLIC_EUROSTRUCT_API_URL`, et le cas
            # reclame une variable qui n'existe pas.
            lues |= set(re.findall(r"(?<![A-Z0-9_])EUROSTRUCT_[A-Z0-9_]+", texte))
            lues |= set(re.findall(r"(?<![A-Z0-9_])NEXT_PUBLIC_[A-Z0-9_]+", texte))

    manquantes = sorted(lues - declarees)
    assert not manquantes, (
        f"variables lues par le code et absentes du gabarit: {manquantes}. "
        "Elles ne se manifesteront qu'au deploiement."
    )
