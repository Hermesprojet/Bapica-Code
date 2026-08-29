#!/usr/bin/env python3
"""Barrière d'architecture : par où un module produit peut obtenir un provider.

CE QUE CETTE BARRIERE EST, ET N'EST PAS
----------------------------------------
C'est une barrière d'**architecture**, pas une preuve d'authentification
réelle. Elle ne dit rien de qui valide un jeton ; elle dit qu'aucun module
produit ne peut se procurer un provider autrement que par la factory.

ELLE NE FIGE PAS L'ABSENCE DE CONSOMMATEUR. Il n'existe aujourd'hui aucun
consommateur produit — mesuré — mais un contrôle qui exigerait éternellement
« zéro consommateur » interdirait le jour où l'on en écrit un. La règle porte
sur la **manière**, pas sur le nombre : un futur consommateur qui passe par
``creer_provider_de_production`` est accepté.

CE QUI EST INTERDIT DANS UN MODULE PRODUIT
-------------------------------------------
1. construire ``InMemoryConfirmationProvider`` ;
2. construire ``PostgresConfirmationProvider`` directement, sans la factory ;
3. importer un authentificateur de fixture (module de tests) ;
4. transmettre un acteur brut à une primitive du provider ;
5. transformer un échec de configuration en repli mémoire.

POURQUOI L'AST, ET PAS `grep`
------------------------------
Un ``grep`` sur le nom de la classe se contourne en une ligne :

    from ...confirmation import InMemoryConfirmationProvider as P
    P()

L'analyse syntaxique suit les **alias d'import** et retrouve la classe
réellement instanciée. Elle voit aussi la construction indirecte par
``getattr(module, "InMemoryConfirmationProvider")``.

Rend 0 si aucun manquement, 1 sinon.
"""
from __future__ import annotations

import ast
import pathlib
import sys

#: Ce que nul module produit ne construit lui-même.
CLASSES_INTERDITES = {
    "InMemoryConfirmationProvider",
    "PostgresConfirmationProvider",
}

#: Le seul chemin autorisé.
FACTORY = "creer_provider_de_production"

#: Modules qui DEFINISSENT la frontière, et sont donc exemptés — ils ont le
#: droit de nommer ce qu'ils encadrent. Tout autre module produit est soumis.
DEFINISSENT_LA_FRONTIERE = {
    "confirmation.py",      # définit le Protocol et le provider mémoire
    "postgres_provider.py",  # définit le provider PostgreSQL
    "provider_factory.py",   # définit la factory elle-même
}


class Inspecteur(ast.NodeVisitor):
    """Suit les alias d'import puis relève les constructions interdites."""

    def __init__(self, fichier: str) -> None:
        self.fichier = fichier
        self.alias: dict[str, str] = {}      # nom local -> nom d'origine
        self.manquements: list[str] = []
        self.passe_par_la_factory = False

    # -- imports ----------------------------------------------------------
    def visit_ImportFrom(self, noeud: ast.ImportFrom) -> None:
        for a in noeud.names:
            local = a.asname or a.name
            self.alias[local] = a.name
            if a.name == FACTORY:
                self.passe_par_la_factory = True
            module = noeud.module or ""
            # UN AUTHENTIFICATEUR DE FIXTURE N'ENTRE PAS DANS UN MODULE PRODUIT.
            #
            # LA REGLE ETAIT TROP ETROITE, ET LES FIXTURES L'ONT MONTRE. Elle
            # exigeait le segment EXACT « test » ou le suffixe « _fixtures »:
            # `ndp.test_doubles` passait. Ma falsification manuelle avait pris
            # par hasard la seule convention couverte — c'est exactement la
            # faute qui a produit les onze survivants, prouver une garantie
            # avec l'exemple qu'elle couvre deja.
            #
            # On reconnait desormais les conventions reellement employees.
            segments = module.split(".")
            suspect = any(
                s.startswith("test") or s.endswith("_test")
                or any(m in s for m in ("fixture", "double", "stub", "fake",
                                        "mock", "leurre", "factice"))
                for s in segments)
            if suspect:
                self.manquements.append(
                    f"{self.fichier}:{noeud.lineno}: import depuis un module de "
                    f"test ({module}.{a.name})")
        self.generic_visit(noeud)

    def visit_Import(self, noeud: ast.Import) -> None:
        for a in noeud.names:
            self.alias[a.asname or a.name] = a.name
        self.generic_visit(noeud)

    # -- constructions ----------------------------------------------------
    def _nom_appele(self, f: ast.expr) -> str:
        if isinstance(f, ast.Name):
            return self.alias.get(f.id, f.id)
        if isinstance(f, ast.Attribute):
            return f.attr
        return ""

    def visit_Call(self, noeud: ast.Call) -> None:
        nom = self._nom_appele(noeud.func)
        if nom in CLASSES_INTERDITES:
            self.manquements.append(
                f"{self.fichier}:{noeud.lineno}: construction directe de {nom} "
                f"— passer par {FACTORY}()")
        # CONSTRUCTION INDIRECTE: getattr(module, "…Provider")()
        if nom == "getattr" and len(noeud.args) >= 2:
            cible = noeud.args[1]
            if isinstance(cible, ast.Constant) and cible.value in CLASSES_INTERDITES:
                self.manquements.append(
                    f"{self.fichier}:{noeud.lineno}: construction indirecte de "
                    f"{cible.value} par getattr")
        # ACTEUR BRUT: aucune primitive du provider ne reçoit d'acteur.
        for mc in noeud.keywords:
            if mc.arg in {"actor_id", "acteur", "proposer_id", "approver_id"}:
                self.manquements.append(
                    f"{self.fichier}:{noeud.lineno}: acteur brut « {mc.arg} » "
                    f"transmis — l'identite vient de l'authentificateur")
        self.generic_visit(noeud)

    # -- repli mémoire ----------------------------------------------------
    def visit_ExceptHandler(self, noeud: ast.ExceptHandler) -> None:
        for sous in ast.walk(noeud):
            if isinstance(sous, ast.Call):
                nom = self._nom_appele(sous.func)
                if nom == "InMemoryConfirmationProvider":
                    self.manquements.append(
                        f"{self.fichier}:{sous.lineno}: repli memoire dans un "
                        f"gestionnaire d'exception — un echec de configuration "
                        f"n'est pas une autorisation")
        self.generic_visit(noeud)


def inspecter(chemin: pathlib.Path) -> list[str]:
    if chemin.name in DEFINISSENT_LA_FRONTIERE:
        return []
    try:
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    except SyntaxError as e:
        return [f"{chemin.name}: illisible ({e})"]
    insp = Inspecteur(chemin.name)
    insp.visit(arbre)
    return insp.manquements


def main(argv: list[str]) -> int:
    racines = [pathlib.Path(a) for a in argv[1:]] or [pathlib.Path(".")]
    manquements: list[str] = []
    fichiers: list[pathlib.Path] = []
    for racine in racines:
        # UN CHEMIN DE FICHIER EST ACCEPTE, ET C'EST UNE CORRECTION MESUREE:
        # `rglob` sur un fichier ne rend RIEN, la barriere inspectait zero
        # module et annoncait « aucun manquement ». Un controle qui n'a rien
        # regarde ne doit jamais rendre vert.
        if racine.is_file():
            fichiers.append(racine)
        else:
            fichiers.extend(sorted(racine.rglob("*.py")))
    fichiers = [f for f in fichiers if "__pycache__" not in f.parts]
    if not fichiers:
        print("REFUS: aucun module Python a inspecter — un controle qui ne "
              "regarde rien ne vaut pas un controle reussi.", file=sys.stderr)
        return 2
    n = len(fichiers)
    for f in fichiers:
        manquements.extend(inspecter(f))
    for m in manquements:
        print(m)
    if not manquements:
        print(f"barriere du provider: {n} module(s) inspecte(s), aucun manquement")
    return 1 if manquements else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
