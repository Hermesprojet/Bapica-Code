"""L'empreinte d'implémentation : elle désigne la SÉMANTIQUE EXÉCUTABLE.

CE QU'ELLE A REMPLACÉ D'ABORD
------------------------------
``implementation_payload`` était construit à partir d'``implementation_note``,
une chaîne fournie par le client. Deux rédactions du même paramètre signaient
deux sujets, et le code pouvait changer entièrement sous une confirmation sans
l'invalider.

CE QU'ELLE CORRIGE MAINTENANT, ET POURQUOI C'ÉTAIT ENCORE INSUFFISANT
-----------------------------------------------------------------------
La première correction hachait le **texte source de trois symboles racines**.
Deux défauts, mesurés :

1. **elle ne suivait pas les appels.** ``design_flexure`` est un
   orchestrateur : il lit ``ParameterSet.find``, calcule ``Concrete.fcd`` et
   ``Reinforcement.fyd``, conclut par ``moment_resistance``. C'est là que
   vivent les nombres. Corriger ``fcd`` changeait tous les résultats du pays
   sans déplacer l'empreinte d'un bit ;

2. **elle hachait du texte.** Un commentaire ajouté, une docstring corrigée,
   un passage de formateur invalidaient toutes les confirmations. Une
   empreinte qui bouge pour rien finit par être contournée — ce qui vaut moins
   qu'une empreinte absente, parce que celle-là inspire confiance.

CE QU'ELLE RÉSUME AUJOURD'HUI
-------------------------------
La **fermeture transitive** des racines déclarées, calculée sur l'AST, et de
chaque symbole atteint : sa forme sémantique — l'arbre syntaxique **sans
docstring, sans commentaire, sans position** — plus la valeur des constantes de
module réellement lues.

Deux sources qui ne diffèrent que par la prose ou la mise en page donnent le
même arbre. Deux sources qui diffèrent d'une opération donnent deux arbres.

COMMENT LES DÉPENDANCES SONT ATTEINTES
----------------------------------------
Par ce que le code **dit de lui-même**, jamais par devinette :

* un nom global — ``moment_resistance``, ``_FCK_MAX_MPA`` — se résout dans les
  globales du module qui le lit ;
* un attribut sur un paramètre annoté — ``concrete.fcd`` où la signature dit
  ``concrete: Concrete`` — se résout par l'annotation ;
* ``self.find`` se résout sur la classe qui porte la méthode ;
* un attribut sur un module importé se résout dans ce module.

Ce qui ne se résout pas vers un objet **de ce paquet** n'est pas suivi : Pint,
la bibliothèque standard et le reste ne sont pas de la sémantique EUROSTRUCT.
Leur version relève de l'identité de build, pas de cette empreinte.

POURQUOI DES RACINES DÉCLARÉES MALGRÉ LA FERMETURE
----------------------------------------------------
Une découverte complète — « quel code lit ce paramètre ? » — se trompe en
silence : un chemin manqué produit une empreinte qui couvre moins qu'elle ne
prétend, et personne ne le voit. Une racine NOMMÉE se trompe bruyamment : une
règle absente n'a pas d'empreinte du tout et ne peut pas être confirmée.

La fermeture, elle, ne devine rien : elle suit des références écrites dans le
code. C'est la combinaison qui tient — on déclare **par où l'on entre**, et la
machine trouve **jusqu'où cela va**.

CE QUE L'EMPREINTE FAIT QUAND LE CODE CHANGE
----------------------------------------------
Elle change. Une confirmation antérieure **reste dans l'historique** — elle est
authentique, elle a eu lieu — mais elle n'ouvre plus le mode strict : elle
atteste d'un code qui n'est plus celui qui tourne. La passerelle recalcule
l'empreinte de son côté et refuse l'écart en le nommant.

CE QUI RESTE HUMAIN
--------------------
La déclaration et les citations. Elles portent la PREUVE : ce qu'une personne
a lu, à quelle page, et ce qu'elle certifie. Elles peuvent tout changer de la
preuve, et rien de la spécification ni de l'empreinte d'implémentation.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import inspect
from functools import lru_cache
from typing import Any

from .canonical import CANONICALIZATION_VERSION, Digest, digest_of
from .confirmation import ConfirmationDomainError

__all__ = [
    "CHEMIN_DE_CODE",
    "PAQUET",
    "empreinte_implementation",
    "fermeture_du_chemin",
    "regles_avec_implementation",
]

#: LA FERMETURE S'ARRETE AU BORD DU PAQUET. Ce qui vient de Pint, de la
#: bibliotheque standard ou d'ailleurs n'est pas de la semantique EUROSTRUCT:
#: c'est une dependance de BUILD, et son identite est enregistree avec le
#: calcul, pas dans cette empreinte.
PAQUET = "eurostruct_engine"

#: PROFONDEUR MAXIMALE DE LA FERMETURE.
#:
#: Elle n'est pas la pour borner un cout — le graphe est petit et memorise —
#: mais pour que le jour ou une reference circulaire ou une explosion
#: inattendue survient, on obtienne un REFUS nomme plutot qu'un processus qui
#: ne rend jamais la main.
PROFONDEUR_MAX = 64

#: Les racines du calcul EC2 en flexion.
#:
#: ON DECLARE PAR OU L'ON ENTRE, PAS JUSQU'OU CELA VA. `ParameterSet.get` est
#: ce qui va chercher la valeur; `usable_in_strict_mode` est le portillon qui
#: decide si elle a le droit de servir; `design_flexure` est la ou le nombre
#: entre dans une formule. Tout ce qu'ils appellent est trouve par fermeture.
_EC2_FLEXION = (
    "eurostruct_engine.ndp.registry:ParameterSet.get",
    "eurostruct_engine.ndp.model:NationalParameter.usable_in_strict_mode",
    "eurostruct_engine.ec2.beam_flexure:design_flexure",
)

#: LES DEUX PREMIERES RACINES SONT COMMUNES A TOUS LES MODULES.
#:
#: `ParameterSet.get` va chercher la valeur; `usable_in_strict_mode` est le
#: portillon qui decide si elle a le droit de servir. Aucun module ne lit un
#: parametre national autrement, et une confirmation qui ne les couvrirait pas
#: laisserait le portillon changer sans etre invalidee.
_LECTURE = (
    "eurostruct_engine.ndp.registry:ParameterSet.get",
    "eurostruct_engine.ndp.model:NationalParameter.usable_in_strict_mode",
)

#: Les racines des quatre autres chapitres. Chacune est LA FONCTION ou le
#: nombre entre dans une formule; tout ce qu'elle appelle est trouve par
#: fermeture.
_EC2_CISAILLEMENT = (*_LECTURE, "eurostruct_engine.ec2.beam_shear:design_shear")
_EC2_ANCRAGE = (*_LECTURE, "eurostruct_engine.ec2.anchorage:design_anchorage")
_EC2_SERVICE = (
    *_LECTURE, "eurostruct_engine.ec2.serviceability:design_serviceability")
_EC2_FLECHE = (*_LECTURE, "eurostruct_engine.ec2.deflection:check_span_depth")

_EC2_11 = "EN 1992-1-1"

#: rule_id -> les RACINES du code qui le lit et l'applique.
#:
#: UNE REGLE ABSENTE N'A PAS D'EMPREINTE, donc ne peut pas etre confirmee.
#: C'est le comportement fail-closed voulu: ajouter une regle au registre sans
#: dire par ou le code y entre laisserait signer une attestation qui ne couvre
#: rien.
#:
#: MESURE DU 01/09, AU NAVIGATEUR: ce fail-closed FERMAIT LA VERTICALE ENTIERE.
#: Seules les dix regles de flexion etaient declarees; les onze autres que
#: reclament l'effort tranchant, l'ancrage, l'ouverture des fissures et la
#: fleche n'avaient aucun chemin de code, donc aucune empreinte, donc aucune
#: confirmation possible. Le mode strict ne pouvait pas s'ouvrir pour une
#: verification complete — pas parce qu'un ingenieur n'avait pas releve les
#: valeurs, mais parce que le produit ne savait pas nommer le code qui les
#: applique. Le refus etait juste; c'est la carte qui manquait.
#:
#: UN PARAMETRE PARTAGE PORTE LES RACINES DE CHAQUE MODULE QUI LE LIT.
#: `gamma_C_persistent` sert quatre chapitres sur cinq: une empreinte qui ne
#: couvrirait que la flexion laisserait corriger `design_shear` sous une
#: confirmation acquise, sans l'invalider.
def _chemins() -> dict[str, tuple[str, ...]]:
    par_regle: dict[str, list[str]] = {}
    modules = (
        (_EC2_FLEXION, ("gamma_C_persistent", "gamma_S_persistent",
                        "gamma_C_accidental", "gamma_S_accidental",
                        "alpha_cc", "k1_redistribution", "k2_redistribution",
                        "As_min_coeff", "As_min_floor", "As_max_ratio")),
        (_EC2_CISAILLEMENT, ("gamma_C_persistent", "gamma_S_persistent",
                             "gamma_C_accidental", "gamma_S_accidental",
                             "alpha_cc", "C_Rd_c_coeff", "v_min_coeff",
                             "k1_shear", "cot_theta_min")),
        (_EC2_ANCRAGE, ("gamma_C_persistent", "gamma_S_persistent",
                        "gamma_C_accidental", "gamma_S_accidental",
                        "alpha_ct")),
        (_EC2_SERVICE, ("k1_stress_limit", "k3_steel_stress", "w_max",
                        "k3_crack_spacing", "k4_crack_spacing")),
        (_EC2_FLECHE, ("K_span_depth",)),
    )
    for racines, noms in modules:
        for nom in noms:
            # DEDUPLIQUE ET ORDONNE: l'empreinte se calcule sur cette liste, et
            # deux ordres differents pour un meme ensemble de racines
            # donneraient deux empreintes pour un meme code.
            atteintes = par_regle.setdefault(f"{_EC2_11}:{nom}", [])
            for r in racines:
                if r not in atteintes:
                    atteintes.append(r)
    return {regle: tuple(sorted(racines))
            for regle, racines in par_regle.items()}


CHEMIN_DE_CODE: dict[str, tuple[str, ...]] = _chemins()


def regles_avec_implementation() -> tuple[str, ...]:
    """Les règles dont les racines sont déclarées. Pour les diagnostics."""
    return tuple(sorted(CHEMIN_DE_CODE))


# ===========================================================================
# RESOLUTION D'UN SYMBOLE
# ===========================================================================
def _resoudre(symbole: str) -> Any:
    """``"module:Qualname"`` -> l'objet, ou un refus qui nomme ce qui manque."""
    module_nom, _, qualname = symbole.partition(":")
    if not module_nom or not qualname:
        raise ConfirmationDomainError(
            f"symbole {symbole!r} mal forme: attendu « module:Qualname »."
        )
    try:
        objet = importlib.import_module(module_nom)
    except ImportError as cause:
        raise ConfirmationDomainError(
            f"le chemin de code declare cite le module {module_nom!r}, "
            "introuvable. L'empreinte d'implementation ne peut pas etre "
            "calculee, et on ne la devine pas."
        ) from cause
    for morceau in qualname.split("."):
        try:
            objet = inspect.getattr_static(objet, morceau)
        except AttributeError as cause:
            raise ConfirmationDomainError(
                f"le chemin de code declare cite {symbole!r}, et "
                f"{morceau!r} n'existe pas. Un chemin qui ne resout plus "
                "designe un code qui a bouge sans que la carte suive."
            ) from cause
    return objet


def _deballer(objet: Any) -> Any:
    """``property`` -> son accesseur ; ``staticmethod`` -> la fonction.

    ``getattr_static`` rend l'objet du dictionnaire de classe, si bien qu'une
    ``property`` arrive telle quelle : on prend son accesseur, qui est le code
    réellement exécuté.
    """
    if isinstance(objet, property):
        objet = objet.fget
    return getattr(objet, "__func__", objet)


def _source_du_symbole(symbole: str) -> str:
    """Le TEXTE SOURCE du symbole désigné.

    C'EST LE POINT UNIQUE PAR LEQUEL TOUTE SOURCE PASSE, et c'est délibéré :
    les preuves déplacent la source ici pour simuler un correctif, sans
    réécrire le moteur.
    """
    cible = symbole.rsplit(":", 1)[-1]
    objet = _deballer(_resoudre(symbole))
    try:
        return inspect.getsource(objet)
    except (OSError, TypeError) as cause:
        raise ConfirmationDomainError(
            f"la source de {cible!r} n'est pas lisible ({type(cause).__name__}). "
            "Sans elle, l'empreinte d'implementation ne resumerait rien; on "
            "refuse plutot que d'en fabriquer une."
        ) from cause


# ===========================================================================
# LA FORME SEMANTIQUE
# ===========================================================================
def _sans_docstring(noeud: ast.AST) -> ast.AST:
    """Retire la docstring de chaque fonction, classe et module de l'arbre.

    UNE DOCSTRING EST UNE CONSTANTE DANS L'AST, contrairement aux commentaires
    qui n'y entrent jamais. Sans ce retrait, préciser un ``:param:`` ferait
    tomber toutes les confirmations du pays — le cas le plus fréquent en
    pratique, et le plus injustifiable.
    """
    for n in ast.walk(noeud):
        if not isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef
                          | ast.ClassDef | ast.Module):
            continue
        corps = n.body
        if (corps and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)
                and isinstance(corps[0].value.value, str)):
            # UN CORPS NE PEUT PAS ETRE VIDE. Une fonction dont la docstring
            # etait l'unique instruction devient `pass`, ce qui a exactement
            # la meme semantique.
            n.body = corps[1:] or [ast.Pass()]
    return noeud


def _arbre(symbole: str) -> ast.AST:
    """L'AST du symbole, désindenté puis analysé.

    ``inspect.getsource`` d'une méthode rend un bloc indenté, que ``ast.parse``
    refuse. On le désindente — ce qui est une opération de **lecture**, pas une
    normalisation sémantique : le résultat est le même code.

    LA MARGE EST CELLE DE LA PREMIÈRE LIGNE, pas le préfixe commun.
    ``textwrap.dedent`` calcule le plus grand préfixe partagé par TOUTES les
    lignes non vides ; une seule ligne à la colonne zéro le ramène à rien, et
    la méthode reste indentée — ``ast.parse`` répond alors « unexpected
    indent » sur du code parfaitement valide. Mesuré. La marge du ``def`` est
    la bonne réponse : c'est elle qui définit le bloc.
    """
    brut = _source_du_symbole(symbole)
    premiere = brut.lstrip("\n").split("\n", 1)[0]
    marge = premiere[:len(premiere) - len(premiere.lstrip())]
    source = brut
    if marge:
        source = "\n".join(
            ligne[len(marge):] if ligne.startswith(marge) else ligne.lstrip()
            for ligne in brut.split("\n"))
    try:
        return ast.parse(source)
    except SyntaxError as cause:
        raise ConfirmationDomainError(
            f"la source de {symbole!r} ne s'analyse pas ({cause}). Une "
            "empreinte calculee sur du code qu'on ne sait pas lire ne "
            "resumerait rien."
        ) from cause


def _semantique(symbole: str) -> str:
    """La forme canonique du symbole : son arbre, sans prose ni position.

    ``include_attributes=False`` retire les numéros de ligne et de colonne :
    réindenter, aérer ou déplacer la fonction dans son fichier ne change rien.
    Les commentaires n'entrent jamais dans un AST. Les docstrings sont
    retirées par ``_sans_docstring``.

    CE QUI RESTE EST CE QUI S'EXÉCUTE — noms, opérateurs, littéraux, structure
    de contrôle. Deux sources qui produisent le même arbre produisent le même
    comportement.
    """
    return ast.dump(_sans_docstring(_arbre(symbole)),
                    annotate_fields=True, include_attributes=False)


# ===========================================================================
# LA FERMETURE TRANSITIVE
# ===========================================================================
def _identite(objet: Any) -> str | None:
    """``"module:Qualname"`` d'un objet **de ce paquet**, ou ``None``.

    ``None`` n'est pas un échec : c'est « hors périmètre ». Pint et la
    bibliothèque standard tombent ici, et c'est voulu.
    """
    objet = _deballer(objet)
    module = getattr(objet, "__module__", None)
    qualname = getattr(objet, "__qualname__", None)
    if not module or not qualname:
        return None
    if module != PAQUET and not module.startswith(PAQUET + "."):
        return None
    if "<locals>" in qualname:
        # UNE FERMETURE LOCALE N'A PAS DE CHEMIN STABLE. Son code est
        # forcement inclus dans celui de la fonction qui la porte, donc deja
        # couvert: la suivre separement n'ajouterait rien et casserait la
        # resolution.
        return None
    return f"{module}:{qualname}"


def _annotations_locales(arbre: ast.AST, symbole: str) -> dict[str, Any]:
    """Ce que le code DIT du type de ses variables. Rien de plus.

    Les paramètres annotés — ``concrete: Concrete`` — et ``self``/``cls`` sur
    une méthode. C'est ce qui permet d'atteindre ``Concrete.fcd``, appelée sur
    un paramètre : sans annotation, aucune analyse statique honnête ne peut
    savoir de quel type il s'agit, et deviner serait pire que ne rien suivre.
    """
    module_nom, _, qualname = symbole.partition(":")
    module = importlib.import_module(module_nom)
    globales = vars(module)
    env: dict[str, Any] = {}

    # `self` ET `cls`: la classe qui porte la methode. C'est ce qui fait
    # atteindre `ParameterSet.find` depuis `ParameterSet.get`.
    if "." in qualname:
        proprietaire = globales.get(qualname.rsplit(".", 1)[0])
        if proprietaire is not None:
            env["self"] = proprietaire
            env["cls"] = proprietaire

    for n in ast.walk(arbre):
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef):
            args = n.args
            for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
                nom = _nom_annote(a.annotation)
                if nom and nom in globales:
                    env[a.arg] = globales[nom]
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            nom = _nom_annote(n.annotation)
            if nom and nom in globales:
                env[n.target.id] = globales[nom]
    return env


def _nom_annote(annotation: ast.expr | None) -> str | None:
    """Le nom nu d'une annotation, en traversant ``X | None`` et ``"X"``.

    ``from __future__ import annotations`` transforme toute annotation en
    chaîne à l'exécution, mais l'AST la garde telle qu'écrite : on la lit là.
    """
    if annotation is None:
        return None
    if isinstance(annotation, ast.Name):
        return annotation.id
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        return annotation.value.split("|")[0].strip().strip('"\'') or None
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        # `Concrete | None` -> `Concrete`. On ne suit que la partie gauche:
        # `None` n'a pas de code, et une union de deux types du paquet est un
        # cas que ce moteur n'a pas.
        return _nom_annote(annotation.left)
    if isinstance(annotation, ast.Attribute):
        return annotation.attr
    return None


def _references(symbole: str) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    """Ce que ce symbole atteint : ses dépendances, et ses constantes lues.

    Rend ``(symboles, constantes)``. Une constante est un nom de module lié à
    une valeur non appelable — ``_FCK_MAX_MPA = 50.0`` — et sa VALEUR compte :
    porter le seuil de 50 à 60 MPa change ce que le moteur accepte, sans
    changer une seule ligne de code exécutable.
    """
    arbre = _arbre(symbole)
    module_nom = symbole.partition(":")[0]
    globales = vars(importlib.import_module(module_nom))
    env = _annotations_locales(arbre, symbole)

    trouves: set[str] = set()
    constantes: set[tuple[str, str]] = set()

    def _noter(objet: Any, nom_lisible: str) -> None:
        identite = _identite(objet)
        if identite is not None:
            trouves.add(identite)
            return
        # PAS UN OBJET DE CODE DU PAQUET. Si c'est une valeur de module — un
        # seuil, une chaine de norme — sa VALEUR entre dans l'empreinte.
        if (nom_lisible in globales and not callable(objet)
                and not inspect.ismodule(objet)
                and isinstance(objet, str | int | float | bool | tuple | frozenset)):
            constantes.add((f"{module_nom}:{nom_lisible}", repr(objet)))

    for n in ast.walk(arbre):
        if isinstance(n, ast.Name):
            if n.id in globales:
                _noter(globales[n.id], n.id)
        elif isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
            base = n.value.id
            porteur = env.get(base)
            if porteur is None and base in globales:
                porteur = globales[base]
            if porteur is None:
                continue
            try:
                membre = inspect.getattr_static(porteur, n.attr)
            except AttributeError:
                # UN ATTRIBUT QUI N'EXISTE PAS STATIQUEMENT N'EST PAS UNE
                # DEPENDANCE MANQUANTE: c'est un attribut d'instance, ou une
                # methode d'un objet tiers. Le suivre serait deviner.
                continue
            _noter(membre, f"{base}.{n.attr}")

    return tuple(sorted(trouves)), tuple(sorted(constantes))


@lru_cache(maxsize=64)
def fermeture_du_chemin(
    racines: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    """La fermeture transitive des racines, et les constantes qu'elle lit.

    PARCOURS EN LARGEUR, ORDRE STABLE. Le résultat est trié : deux exécutions
    du même dépôt rendent la même liste, sans quoi l'empreinte dépendrait de
    l'ordre d'un ``set``.

    :raises ConfirmationDomainError: un symbole atteint appartient au paquet
        et sa source est illisible — refus fail-closed. Hacher « ce qu'on a pu
        lire » produirait une empreinte qui couvre moins qu'elle ne prétend, et
        personne ne le verrait.
    """
    vus: set[str] = set()
    constantes: set[tuple[str, str]] = set()
    a_voir = list(racines)
    profondeur = 0

    while a_voir:
        profondeur += 1
        if profondeur > PROFONDEUR_MAX:
            raise ConfirmationDomainError(
                f"la fermeture du chemin de code depasse {PROFONDEUR_MAX} "
                "iterations. Plutot que de rendre une empreinte partielle, on "
                "refuse: une empreinte qui couvre moins qu'elle ne pretend est "
                "pire qu'une empreinte absente."
            )
        suivants: list[str] = []
        for symbole in a_voir:
            if symbole in vus:
                continue
            vus.add(symbole)
            # `_references` LIT LA SOURCE, donc leve si elle est illisible.
            # C'est le refus fail-closed, et il vient du chemin normal.
            refs, consts = _references(symbole)
            constantes.update(consts)
            suivants.extend(r for r in refs if r not in vus)
        a_voir = suivants

    return tuple(sorted(vus)), tuple(sorted(constantes))


# ===========================================================================
# L'EMPREINTE
# ===========================================================================
@lru_cache(maxsize=256)
def empreinte_implementation(rule_id: str) -> Digest:
    """L'empreinte du code qui lit et applique ``rule_id``.

    UN SEUL PARAMÈTRE, ET C'EST LA GARANTIE. Il n'y a aucune façon de faire
    entrer un texte ici : ce qui est haché sort du dépôt.

    ``engine_version`` FIGURE DANS LE PAYLOAD SANS EN ÊTRE LA SUBSTANCE. Elle
    situe l'empreinte ; ce sont les arbres sémantiques qui la déterminent. Six
    commits successifs partagent la même version — mesuré — donc elle ne
    désigne aucun code à elle seule.

    :raises ConfirmationDomainError: aucune racine n'est déclarée pour cette
        règle, un symbole déclaré ne résout plus, ou une dépendance interne
        atteinte est illisible.
    """
    from ..version import ENGINE_NAME, ENGINE_VERSION

    racines = CHEMIN_DE_CODE.get(rule_id)
    if not racines:
        raise ConfirmationDomainError(
            f"aucun chemin de code n'est declare pour {rule_id!r}. Une regle "
            "dont on ne sait pas nommer le code qui l'applique ne peut pas "
            "etre confirmee: l'attestation ne couvrirait rien. Declarer les "
            "racines dans ndp/implementation.py, ou retirer la regle."
        )
    symboles, constantes = fermeture_du_chemin(racines)
    return digest_of({
        "kind": "implementation",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "rule_id": rule_id,
        "engine_name": ENGINE_NAME,
        "engine_version": ENGINE_VERSION,
        # LES RACINES SONT NOMMEES A PART. Elles disent ce qui a ete DECLARE;
        # `code_path` dit ce qui a ete ATTEINT. Confondre les deux ferait
        # perdre l'information qui explique une empreinte surprenante.
        "roots": list(racines),
        # TRIE, ET C'EST NECESSAIRE. L'ordre d'un parcours de graphe n'est pas
        # une propriete du code: le laisser entrer ferait bouger l'empreinte
        # sans qu'aucune ligne ne change.
        "code_path": [
            {"symbol": s,
             "semantics_sha256": hashlib.sha256(
                 _semantique(s).encode("utf-8")).hexdigest()}
            for s in symboles
        ],
        # LES CONSTANTES LUES, PAR VALEUR. Porter `_FCK_MAX_MPA` de 50 a 60
        # change le domaine de validation sans changer une ligne executable.
        "constants": [{"symbol": s, "value": v} for s, v in constantes],
    })
