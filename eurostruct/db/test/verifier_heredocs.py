#!/usr/bin/env python3
"""Deux defauts de composition du SQL par le shell, dans les harnais.

DEFAUT 1 — L'HEREDOC NON QUOTE QUI CONTIENT UNE SUBSTITUTION
-------------------------------------------------------------
Un heredoc ouvert par ``<<SQL`` — et non ``<<'SQL'`` — subit l'expansion du
shell. Ce qui ressemble a de la prose SQL est alors du shell. Mesure du 28/08 :

    montrer <<SQL
    -- voir `whoami` pour le detail
    SQL

fait parvenir a ``psql`` la ligne ``-- voir root pour le detail``. La
substitution s'execute, et sa sortie entre dans le flux SQL. Quatre harnais
d'autorite contenaient cette forme.

Une substitution ECHAPPEE (``\\`` ou ``\\$(``) n'est pas ce defaut : c'est la
forme correcte quand on ECRIT un script par heredoc — ``deploy_recovery.sh``
compose un faux ``psql`` dont le corps doit s'evaluer a l'execution, pas a
l'ecriture. Les compter aurait fait rougir la bonne pratique.

DEFAUT 2 — LA VALEUR LUE DANS LA BASE, RECOLLEE DANS UN LITTERAL SQL
---------------------------------------------------------------------
C'est le defaut le plus repandu, et le scanner ne le voyait pas : il ne
regardait QUE les heredocs, alors que sa forme dominante est ``-c``.

    MANIFESTE=$(ctl -tAc "select normative_settings_manifest()" 2>&1)
    SORTIE=$(ctl   -tAc "select normative_finalize_deployment('$MANIFESTE')")

La valeur ne vient pas du harnais : elle vient de la base. Et le ``2>&1`` la
rend PIRE — en cas d'echec la variable contient un message d'erreur francais,
plein d'apostrophes. Mesure du 29/08, PostgreSQL 16.13 :

    VAL="ERROR:  le plan « x » n'est pas separe"
    insert into trace values ('$VAL');
    -> ERROR:  syntax error at or near "est"        (0 ligne inseree)

    psql -v m="$VAL" ... ; insert into trace values (:'m');
    -> 1 ligne, RECU: ERROR:  le plan « x » n'est pas separe

Le harnais ne mesure alors plus ce qu'il annonce : il lit un refus la ou il y
a une erreur de syntaxe. C'est exactement la faute qui a produit les onze
survivants de la campagne `3d0acc2` — un diagnostic sans rapport avec la cause.

La forme sure est la variable psql, ``-v m="$VAL"`` puis ``:'m'``. psql cite
la valeur lui-meme. Mesure : psql N'INTERPOLE PAS ``:nom`` dans un litteral
simple deja ecrit (``select 'avant :nom apres'`` rend ``avant :nom apres``),
donc la conversion ne peut pas deranger les corps existants.

CE QUI A ETE CONVERTI, ET LE CLIQUET QUI RESTE
-----------------------------------------------
Trente-deux sites preexistaient, dans quinze harnais. Tous sont convertis :
la valeur passe desormais par ``-v esc_v="$VAR"`` et le SQL porte
``:'esc_v'``. Le plafond vaut donc ZERO, et il est conserve comme cliquet :

  * un site de plus  -> rouge (la dette reapparait) ;
  * un plafond non nul alors que le compte a baisse -> rouge aussi, avec la
    valeur a inscrire (un plafond perime ne mesure plus rien).

Le compte tel que le scanner le voit vaut 31, non 32 : ``$mb``, dans la course
D2 de ``authority_closure.sh``, est un PARAMETRE de fonction, pas une variable
affectee depuis la base. Il a ete converti avec les autres — la valeur qu'il
porte vient de la base par ``$ma`` — mais le scanner ne pouvait pas le
designer. Ce que le scanner ne voit pas est ecrit ici plutot que suppose.

Rend 0 si rien n'est trouve, 1 sinon, 2 s'il n'a rien regarde.
"""
from __future__ import annotations

import pathlib
import re
import sys

OUVERTURE = re.compile(r"<<(-?)([A-Za-z_]\w*)\s*$")

#: Fonctions dont la valeur de retour vient de la base, jamais du harnais.
#: Recoller l'une d'elles dans un litteral SQL est le defaut 2.
LUES_DANS_LA_BASE = (
    "normative_settings_manifest",
    "normative_authority_manifest",
)

#: Dette payee le 29/08 sur `db/test`. NE PEUT QUE BAISSER.
PLAFOND_RECOLLAGE = 0


def _corps_heredocs(lignes: list[str]):
    """Rend (ligne_ouverture, delimiteur, texte) pour chaque heredoc."""
    i = 0
    while i < len(lignes):
        m = OUVERTURE.search(lignes[i])
        if not m:
            i += 1
            continue
        delim = m.group(2)
        j, corps = i + 1, []
        while j < len(lignes) and lignes[j].strip() != delim:
            corps.append(lignes[j])
            j += 1
        yield i + 1, delim, "\n".join(corps)
        i = j + 1


def heredocs_a_risque(chemin: pathlib.Path) -> list[tuple[int, str]]:
    """Defaut 1 : heredoc non quote portant une substitution non echappee."""
    lignes = chemin.read_text(encoding="utf-8", errors="replace").split("\n")
    trouves: list[tuple[int, str]] = []
    for ligne, delim, texte in _corps_heredocs(lignes):
        if re.search(r"(?<!\\)`", texte) or re.search(r"(?<!\\)\$\(", texte):
            trouves.append((ligne, delim))
    return trouves


def _variables_lues_dans_la_base(lignes: list[str]) -> set[str]:
    """Les variables shell affectees depuis un appel a une fonction de la base.

    On ne devine pas : on releve `X=$(... normative_settings_manifest() ...)`
    et `X=$(...)` sur plusieurs lignes n'est pas couvert — c'est dit dans le
    rapport plutot que suppose silencieusement.
    """
    noms: set[str] = set()
    motif = re.compile(r"\b([A-Za-z_]\w*)=\$\(")
    for ligne in lignes:
        if not any(f in ligne for f in LUES_DANS_LA_BASE):
            continue
        m = motif.search(ligne)
        if m:
            noms.add(m.group(1))
    return noms


def recollages(chemin: pathlib.Path) -> list[tuple[int, str]]:
    """Defaut 2 : une de ces variables recollee dans un litteral SQL `'...'`.

    Vu partout, heredoc ou `-c` : on cherche la sequence `'$NOM'`, qui est le
    recollage lui-meme, quel que soit le vehicule.
    """
    lignes = chemin.read_text(encoding="utf-8", errors="replace").split("\n")
    noms = _variables_lues_dans_la_base(lignes)
    if not noms:
        return []
    motif = re.compile(r"'\$\{?(" + "|".join(map(re.escape, sorted(noms))) + r")\}?'")
    trouves: list[tuple[int, str]] = []
    for n, ligne in enumerate(lignes, 1):
        for m in motif.finditer(ligne):
            # L'AFFECTATION ELLE-MEME N'EST PAS UN RECOLLAGE.
            if re.search(r"\b[A-Za-z_]\w*=\$\(", ligne[:m.start()]) and \
               all(f not in ligne for f in LUES_DANS_LA_BASE):
                pass
            trouves.append((n, m.group(1)))
    return trouves


def fichiers_a_inspecter(racines: list[pathlib.Path]) -> list[pathlib.Path]:
    """UN CHEMIN DE FICHIER EST ACCEPTE.

    `glob` sur un fichier ne rend RIEN : le scanner inspectait zero fichier et
    annoncait « rien trouve ». Meme faute que la barriere AST, meme correction.
    """
    fichiers: list[pathlib.Path] = []
    for racine in racines:
        if racine.is_file():
            fichiers.append(racine)
        else:
            fichiers.extend(sorted(racine.glob("*.sh")))
    return fichiers


def main(argv: list[str]) -> int:
    racines = [pathlib.Path(a) for a in argv[1:]] or [pathlib.Path(".")]
    fichiers = fichiers_a_inspecter(racines)
    if not fichiers:
        print("REFUS: aucun fichier .sh a inspecter — un controle qui ne "
              "regarde rien ne vaut pas un controle reussi.", file=sys.stderr)
        return 2

    total_h = 0
    for f in fichiers:
        for ligne, delim in heredocs_a_risque(f):
            print(f"{f.name}:{ligne} (<<{delim}) substitution dans un heredoc "
                  f"non quote")
            total_h += 1

    sites: list[tuple[str, int, str]] = []
    for f in fichiers:
        for ligne, nom in recollages(f):
            sites.append((f.name, ligne, nom))

    n = len(sites)
    if n > PLAFOND_RECOLLAGE:
        print(f"REFUS: {n} recollage(s) d'une valeur lue dans la base dans un "
              f"litteral SQL, plafond {PLAFOND_RECOLLAGE}. Les nouveaux sites "
              f"doivent passer par une variable psql (-v m=\"$V\" puis :'m').",
              file=sys.stderr)
        for nom, ligne, v in sites:
            print(f"    {nom}:{ligne}  ${v}", file=sys.stderr)
    elif n < PLAFOND_RECOLLAGE:
        print(f"REFUS: {n} recollage(s) alors que le plafond en annonce "
              f"{PLAFOND_RECOLLAGE}. Un plafond perime ne mesure plus rien : "
              f"inscrire PLAFOND_RECOLLAGE = {n}.", file=sys.stderr)

    if total_h == 0 and n == PLAFOND_RECOLLAGE:
        print(f"composition du SQL: {len(fichiers)} fichier(s), aucune "
              f"substitution en heredoc non quote, {n} recollage(s) connu(s) "
              f"au plafond.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
