#!/usr/bin/env python3
"""Eprouve `verifier_heredocs.py` sur des cas FABRIQUES, jamais sur l'arbre.

POURQUOI DES CAS FABRIQUES
---------------------------
Un scanner qu'on n'eprouve que sur l'arbre reel ne prouve rien : il rend vert
parce que l'arbre est propre, pas parce qu'il sait voir. La faute est
exactement celle qui a produit les onze survivants de `3d0acc2` — prouver une
garantie avec l'exemple qu'elle couvre deja.

Chaque cas ci-dessous porte un VERDICT ATTENDU. Un scanner qui cesse de voir
l'un d'eux fait rougir ce fichier.

LE CAS 10 EST D'UNE AUTRE NATURE
---------------------------------
Les cas 1 a 9 sont des cas d'ANALYSE : on donne un texte au scanner et on
regarde son verdict. Le cas 10 est une MESURE : il fait tourner un vrai shell
et constate ce que la couche cible RECOIT. C'etait le trou connu — le scanner
admettait la forme echappee sans que rien ne prouve qu'elle arrive litterale
la ou elle doit s'evaluer plus tard.

Rend 0 si tous les cas passent, 1 sinon.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

ICI = pathlib.Path(__file__).resolve().parent
SCANNER = ICI / "verifier_heredocs.py"

#: (nom, contenu du .sh, doit_etre_detecte)
CAS: list[tuple[str, str, bool]] = [
    ("1. heredoc non quote, accent grave",
     'montrer <<SQL\n-- voir `whoami` pour le detail\nSQL\n', True),

    ("2. heredoc non quote, $( )",
     'psql <<SQL\nselect $(echo 1);\nSQL\n', True),

    ("3. heredoc QUOTE, accent grave",
     "psql <<'SQL'\n-- voir `whoami` pour le detail\nSQL\n", False),

    ("4. forme ECHAPPEE \\$( ) — la bonne pratique",
     'cat > faux <<SQL\necho "\\$(date)"\nSQL\n', False),

    ("5. ${VAR} simple, sans substitution",
     'psql <<SQL\nselect * from ${TABLE};\nSQL\n', False),

    ("6. ${VAR} contenant une substitution",
     'psql <<SQL\nselect ${A:-$(id -u)};\nSQL\n', True),

    # -- defaut 2: le recollage, dont la forme dominante n'est PAS un heredoc
    ("7. recollage d'une valeur lue dans la base, en -c",
     'M=$(ctl -tAc "select normative_settings_manifest()" 2>&1)\n'
     'S=$(ctl -tAc "select normative_finalize_deployment(\'$M\')" 2>&1)\n', True),

    # LA FORME SURE PASSE PAR L'ENTREE STANDARD, JAMAIS PAR `-c`.
    # Mesure du 29/08: `psql -c "select :'v'"` rend une erreur de syntaxe —
    # psql n'interpole pas ses variables dans une chaine `-c`. Et sans
    # ON_ERROR_STOP, l'entree standard rend ZERO sur une erreur SQL. Ce cas
    # fixe donc la seule forme qui marche, pour qu'aucune relecture ne prenne
    # `-c` + `:'v'` pour la correction.
    ("8. le meme site, en entree standard avec ON_ERROR_STOP",
     'M=$(ctl -tAc "select normative_settings_manifest()" 2>&1)\n'
     'S=$(ctl -v ON_ERROR_STOP=1 -v esc_v="$M" -tA '
     '<<<"select normative_finalize_deployment(:\'esc_v\')" 2>&1)\n', False),

    ("9. recollage dans un HEREDOC (meme defaut, autre vehicule)",
     'M=$(ctl -tAc "select normative_settings_manifest()" 2>&1)\n'
     'ctl <<SQL\nselect normative_finalize_deployment(\'$M\');\nSQL\n', True),
]


def _lancer(cible: pathlib.Path) -> int:
    r = subprocess.run([sys.executable, str(SCANNER), str(cible)],
                       capture_output=True, text=True)
    return r.returncode


def cas_analyse() -> list[str]:
    echecs: list[str] = []
    for nom, contenu, attendu in CAS:
        with tempfile.TemporaryDirectory() as d:
            f = pathlib.Path(d) / "cas.sh"
            f.write_text(contenu, encoding="utf-8")
            rc = _lancer(f)
        detecte = rc == 1
        if detecte != attendu:
            echecs.append(
                f"{nom}: attendu {'DETECTE' if attendu else 'ADMIS'}, "
                f"obtenu {'DETECTE' if detecte else 'ADMIS'} (rc={rc})")
        else:
            print(f"  ok  {nom} -> {'DETECTE' if detecte else 'ADMIS'}")
    return echecs


def cas_10_forme_echappee_recue_litterale() -> list[str]:
    """MESURE: la forme echappee arrive-t-elle LITTERALE a la couche cible ?

    Le scanner ADMET `\\$(date)` dans un heredoc non quote. Cette tolerance
    n'a de sens que si la forme echappee traverse le heredoc SANS s'evaluer,
    et arrive telle quelle dans le fichier ecrit. Rien ne le prouvait.

    On ecrit donc un script par heredoc non quote, exactement comme
    `deploy_recovery.sh` compose son faux `psql`, et on constate DEUX choses:
      a) le fichier ecrit contient `$(date)` en clair, non evalue ;
      b) la forme NON echappee, elle, a bien ete remplacee a l'ecriture.
    Sans (b), (a) pourrait s'expliquer par un heredoc qui n'interpole rien.
    """
    echecs: list[str] = []
    with tempfile.TemporaryDirectory() as d:
        cible = pathlib.Path(d) / "faux_psql"
        script = pathlib.Path(d) / "composer.sh"
        script.write_text(
            'set -u\n'
            'MARQUE=VALEUR_DU_COMPOSITEUR\n'
            f'cat > "{cible}" <<SQL\n'
            'echo "differe: \\$(echo TARDIF)"\n'
            'echo "immediat: $(echo TOT)"\n'
            'echo "marque: $MARQUE"\n'
            'SQL\n', encoding="utf-8")
        r = subprocess.run(["bash", str(script)], capture_output=True, text=True)
        if r.returncode != 0:
            return [f"10. le compositeur a echoue: {r.stderr.strip()[:120]}"]
        ecrit = cible.read_text(encoding="utf-8")

        # (a) la forme echappee est arrivee LITTERALE
        if "$(echo TARDIF)" not in ecrit:
            echecs.append("10a. la forme echappee n'est pas arrivee litterale: "
                          f"{ecrit!r}")
        if "TARDIF\n" in ecrit.replace("$(echo TARDIF)", ""):
            echecs.append("10a. la forme echappee a ete EVALUEE a l'ecriture")

        # (b) le heredoc interpole bien, sinon (a) ne prouverait rien
        if "immediat: TOT" not in ecrit:
            echecs.append("10b. le heredoc n'a pas interpole la forme NON "
                          f"echappee — (a) ne prouve alors rien: {ecrit!r}")
        if "marque: VALEUR_DU_COMPOSITEUR" not in ecrit:
            echecs.append("10b. le heredoc n'a pas interpole $MARQUE")

        # (c) et la couche cible, elle, EVALUE la forme differee
        r2 = subprocess.run(["bash", str(cible)], capture_output=True, text=True)
        if "differe: TARDIF" not in r2.stdout:
            echecs.append("10c. la couche cible n'evalue pas la forme differee: "
                          f"{r2.stdout!r}")
    if not echecs:
        print("  ok  10. forme echappee: litterale a l'ecriture, evaluee par "
              "la couche cible")
    return echecs


def cas_11_refus_sur_rien() -> list[str]:
    """Un scanner qui ne regarde rien ne doit pas rendre vert."""
    echecs: list[str] = []
    with tempfile.TemporaryDirectory() as d:
        rc = _lancer(pathlib.Path(d))
    if rc != 2:
        echecs.append(f"11. repertoire sans .sh: attendu rc=2, obtenu {rc}")
    else:
        print("  ok  11. repertoire sans .sh -> REFUS (rc=2)")
    return echecs


def main() -> int:
    print("selftest du scanner de composition SQL")
    echecs = cas_analyse()
    echecs += cas_10_forme_echappee_recue_litterale()
    echecs += cas_11_refus_sur_rien()
    if echecs:
        print(f"\nECHEC: {len(echecs)} cas", file=sys.stderr)
        for e in echecs:
            print(f"  {e}", file=sys.stderr)
        return 1
    print(f"\n{len(CAS) + 2} cas, tous conformes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
