"""Canonicalisation et empreintes des règles normatives — jalon 6.2.

Trois empreintes, trois questions
----------------------------------
``normative_spec_digest``
    *Quelle règle le pays prescrit.* Indépendante de tout code.

``implementation_digest``
    *Quel code l'exécute.* C'est elle qui empêche qu'une implémentation soit
    modifiée sans que rien ne le signale — le risque n° 1 du jalon 6.1.

``evidence_digest``
    *Ce que le vérificateur a effectivement lu.* Une preuve retouchée après
    signature doit être détectable.

Un seul hash mélangeait les trois. Corriger une virgule dans une citation ne
change pas la mathématique ; changer ``0,6`` en ``0,61`` la change entièrement.

Ce que ce module refuse de faire
---------------------------------
Il **refuse de produire une empreinte d'implémentation** dont la fermeture des
dépendances n'est pas entièrement résolue. Une fermeture incomplète donnerait
une empreinte qui *paraît* couvrir le code sans le couvrir, ce qui est pire que
pas d'empreinte du tout : elle inspirerait une confiance qu'elle ne mérite pas.

La canonicalisation est une opération **pure**
-----------------------------------------------
**Lecture et sérialisation, rien d'autre.** Calculer une empreinte :

- **n'exécute aucun code applicatif** — ni règle, ni décorateur, ni fonction du
  noyau. Tout ce qui est établi sur ce code l'est par analyse de son AST ;
- **ne mute aucun état** — ni les registres de liaison, ni un accumulateur de
  portée module. Les gardes de récursion (``seen``, ``en_cours``) sont passées
  en paramètres ;
- **ne dépend pas de l'ordre** dans lequel les règles sont traitées, ni de ce
  qui a été calculé avant dans le processus.

Une empreinte *décrit* ; elle ne doit rien faire arriver. Ce n'était pas le cas
avant le jalon 6.2c : la preuve d'identité du décorateur ``implementation``
l'**appelait** réellement sur une fonction sonde, ce qui inscrivait cette sonde
dans ``_IMPLEMENTATIONS``. Une restauration explicite annulait l'effet sur les
registres *déclarés* — donc pas un effet de bord ailleurs. Cette preuve est
désormais statique (voir :func:`_preuve_identite_statique`).

Les tests de pureté sont dans ``test_canonical_digests.py``, section 6.2c ; l'un
d'eux relit le source de ce module et **refuse toute mutation d'un conteneur de
portée module**, parce qu'une mutation restaurée par un ``finally`` est nulle en
net et donc invisible à un instantané pris avant et après.

Le payload est conservé, pas seulement haché
---------------------------------------------
Un hash seul ne dit pas, dix ans plus tard, ce qui a été signé. Chaque
:class:`Digest` porte son payload canonique et la version de canonicalisation
qui l'a produit, pour qu'une méthode puisse évoluer sans rendre illisibles les
confirmations anciennes.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import itertools
import json
import math
import textwrap
import unicodedata
from dataclasses import dataclass
from types import FunctionType, ModuleType
from typing import Any

from ..exceptions import EurostructEngineError

__all__ = [
    "CANONICALIZATION_VERSION",
    "Digest",
    "UnresolvableDependency",
    "canonical_json",
    "digest_of",
    "normative_spec_digest",
    "implementation_digest",
    "evidence_digest",
    "ALLOWED_EXTERNAL_SYMBOLS",
    "KERNEL_ALLOWED_SYMBOLS",
    "ALLOWED_EXCEPTIONS",
    "evaluation_kernel_digest",
]

#: Version de la méthode. Elle change dès que la forme canonique change, pour
#: qu'une confirmation ancienne reste interprétable avec la méthode qui l'a
#: produite plutôt que réinterprétée à tort par la nouvelle.
CANONICALIZATION_VERSION = "esc-canon/1"

_ALGORITHM = "sha256"


class UnresolvableDependency(EurostructEngineError):
    """La fermeture des dépendances a rencontré ce qu'elle ne sait pas résoudre.

    Levée plutôt que contournée. Les cas visés — ``getattr`` dynamique, nom
    global introuvable, module hors frontière déclarée — sont exactement ceux
    où une empreinte silencieuse mentirait sur ce qu'elle couvre.
    """


@dataclass(frozen=True, slots=True)
class Digest:
    """Une empreinte, avec de quoi la comprendre sans la recalculer."""

    algorithm: str
    canonicalization_version: str
    canonical_payload: str
    digest: str

    def __eq__(self, other: object) -> bool:
        """Deux empreintes sont égales si leur digest ET leur méthode le sont.

        Comparer les seuls digests laisserait deux versions de
        canonicalisation se croiser sans que rien ne le dise.
        """
        if not isinstance(other, Digest):
            return NotImplemented
        return (
            self.digest == other.digest
            and self.canonicalization_version == other.canonicalization_version
            and self.algorithm == other.algorithm
        )

    def __hash__(self) -> int:
        return hash((self.algorithm, self.canonicalization_version, self.digest))


# ---------------------------------------------------------------------------
# Sérialisation canonique
# ---------------------------------------------------------------------------
def _canonical(value: Any, _chemin: tuple[int, ...] = ()) -> Any:
    """Ramener une valeur à une forme dont la sérialisation est déterministe.

    Garanties, chacune testée :

    **Chaînes** — normalisées en NFC. « é » composé et « e » + accent combinant
    sont visuellement identiques et sont deux suites d'octets différentes : sans
    normalisation, recopier une citation depuis un PDF changerait l'empreinte
    sans que personne ne voie de différence à l'écran.

    **Flottants** — ``repr``, qui donne la plus courte écriture faisant un
    aller-retour exact. ``NaN`` et les infinis sont **refusés** : ils ne
    peuvent pas être le résultat d'une lecture d'annexe, et ``NaN != NaN``
    rendrait toute comparaison d'empreinte fausse en silence. ``-0.0`` est
    ramené à ``0.0`` — les deux sont égaux et se comportent identiquement dans
    les comparaisons de bornes, et les distinguer produirait un changement
    d'empreinte sans changement de sens.

    **``True``, ``1`` et ``1.0``** — trois formes distinctes, délibérément.
    ``True`` sort en booléen JSON, ``1`` en entier, ``1.0`` en
    ``{"__float__": "1.0"}``. Un domaine dont la borne passe de l'entier au
    flottant est un changement de déclaration.

    **Ensembles** — triés sur leur forme canonique **sérialisée**, pas sur
    l'ordre naturel de Python : deux éléments canonicalisés en dictionnaires ne
    sont pas comparables entre eux, et ``sorted`` lèverait.

    **Cycles** — détectés. Un objet qui se contient lui-même ferait autrement
    récurser jusqu'à la pile.
    """
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise UnresolvableDependency(
                f"valeur flottante non finie: {value!r}. Une lecture d'annexe "
                "ne produit ni NaN ni infini, et NaN != NaN rendrait toute "
                "comparaison d'empreinte fausse en silence."
            )
        if value == 0.0:
            value = 0.0          # ramène -0.0 sur 0.0
        return {"__float__": repr(value)}

    ident = id(value)
    if ident in _chemin:
        raise UnresolvableDependency(
            "cycle dans la valeur a canonicaliser: un objet se contient "
            "lui-meme, directement ou non."
        )
    chemin = _chemin + (ident,)

    if hasattr(value, "magnitude") and hasattr(value, "units"):
        m = float(value.magnitude)
        if math.isnan(m) or math.isinf(m):
            raise UnresolvableDependency(
                f"grandeur non finie: {value!r}."
            )
        if m == 0.0:
            m = 0.0
        return {
            "__quantity__": {
                "magnitude": repr(m),
                "units": unicodedata.normalize("NFC", str(value.units)),
            }
        }
    if isinstance(value, Digest):
        return {"__digest__": value.digest,
                "canonicalization_version": value.canonicalization_version}
    if isinstance(value, (list, tuple)):
        return [_canonical(v, chemin) for v in value]
    if isinstance(value, (set, frozenset)):
        # Trier sur la forme SERIALISEE: les elements canonicalises peuvent
        # etre des dictionnaires, que Python refuse de comparer entre eux.
        paires = [
            (json.dumps(e, sort_keys=True, separators=(",", ":"),
                        ensure_ascii=False), e)
            for e in (_canonical(v, chemin) for v in value)
        ]
        paires.sort(key=lambda pair: pair[0])
        for (cle_a, _), (cle_b, _) in itertools.pairwise(paires):
            if cle_a == cle_b:
                raise UnresolvableDependency(
                    f"deux elements distincts de l'ensemble ont la meme forme "
                    f"canonique {cle_a!r} — typiquement deux ecritures Unicode "
                    "de la meme chaine. L'ensemble canonicalise aurait moins "
                    "d'elements que l'original, en silence."
                )
        return [e for _, e in paires]
    if isinstance(value, dict):
        # Normaliser AVANT de trier. Trier sur la forme brute puis normaliser
        # aurait donne un ordre defini sur une forme que le payload ne contient
        # pas — et surtout, deux cles distinctes en Python (« é » compose et
        # « e » + accent combinant) se seraient ecrasees l'une l'autre dans la
        # comprehension, sans un mot.
        normalisees: list[tuple[str, Any]] = [
            (unicodedata.normalize("NFC", str(k)), v) for k, v in value.items()
        ]
        normalisees.sort(key=lambda kv: kv[0])
        for (cle_a, _), (cle_b, _) in itertools.pairwise(normalisees):
            if cle_a == cle_b:
                raise UnresolvableDependency(
                    f"deux cles distinctes se normalisent toutes deux en "
                    f"{cle_a!r}. L'une aurait ecrase l'autre en silence: "
                    "refus explicite."
                )
        return {k: _canonical(v, chemin) for k, v in normalisees}
    if hasattr(value, "value") and hasattr(value, "name"):      # Enum
        return {"__enum__": f"{type(value).__name__}.{value.name}",
                "value": _canonical(value.value, chemin)}
    raise UnresolvableDependency(
        f"valeur non canonicalisable: {type(value).__name__}. Ajouter une "
        "règle de sérialisation explicite plutôt que de la laisser tomber "
        "dans une représentation par défaut."
    )


def canonical_json(payload: Any) -> str:
    """JSON canonique : clés triées, séparateurs fixes, pas d'échappement ASCII."""
    # ensure_ascii=False: les chaines sortent en UTF-8 reel, deja normalisees
    # NFC par _canonical. Le digest est calcule sur l'encodage UTF-8 de cette
    # chaine, jamais sur sa representation interne Python.
    return json.dumps(
        _canonical(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def digest_of(payload: Any) -> Digest:
    text = canonical_json(payload)
    return Digest(
        algorithm=_ALGORITHM,
        canonicalization_version=CANONICALIZATION_VERSION,
        canonical_payload=text,
        digest=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


# ---------------------------------------------------------------------------
# 1. Empreinte de spécification normative
# ---------------------------------------------------------------------------
def _spec_payload(
    rule: Any, seen: dict[str, Digest], en_cours: frozenset[str] | set[str],
) -> dict[str, Any]:
    """Ce que le pays prescrit. Sans description, sans notes, sans citation.

    Exclus délibérément :

    ``description``, ``notes``, ``tests``
        prose de travail ; les modifier n'a aucun effet normatif.
    ``display_unit``
        présentation.
    ``page_pdf``, ``page_printed``, ``quote``
        preuve, pas prescription — elles vont dans l'empreinte de preuve.
    """
    from .rules import ConditionalRule, ScalarRule

    payload: dict[str, Any] = {
        "kind": "normative_spec",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "rule_id": rule.rule_id,
        "rule_type": rule.rule_type.value,
        "output_unit": rule.output_unit,
        "value_provenance": rule.value_provenance.value,
        "inputs": [
            {"name": i.name, "dimension": i.dimension} for i in rule.inputs
        ],
        "domain": [
            {
                "variable": d.variable,
                "minimum": d.minimum,
                "maximum": d.maximum,
                "minimum_inclusive": d.minimum_inclusive,
                "maximum_inclusive": d.maximum_inclusive,
                "maximum_of": d.maximum_of,
                "maximum_factor": d.maximum_factor,
            }
            for d in rule.domain
        ],
        "expression_sources": [
            {
                "reference": s.reference,
                "layer": s.layer,
                "clause": s.clause,
                "expression_label": s.expression_label,
                "effect": s.effect,
                "document_digest": s.doc_id_sha256,
            }
            for s in rule.expression_sources
        ],
        "normative_authority": {
            "country_code": rule.normative_authority.country_code,
            "reference": rule.normative_authority.reference,
            "edition": rule.normative_authority.edition,
            "clause": rule.normative_authority.clause,
            "effect": rule.normative_authority.effect,
            "document_digest": rule.normative_authority.doc_id_sha256,
        },
    }

    if isinstance(rule, ScalarRule):
        payload["scalar_value"] = rule.value

    if isinstance(rule, ConditionalRule):
        # D5: les DIGESTS EXACTS des dépendances, jamais leurs seuls rule_id.
        # Sans cela, modifier alpha_cw_linear laisserait alpha_cw confirmée.
        payload["selector"] = _child_spec_digest(rule.selector_rule_id, seen, en_cours)
        payload["branches"] = [
            {
                "lower": b.lower,
                "upper": b.upper,
                "lower_inclusive": b.lower_inclusive,
                "upper_inclusive": b.upper_inclusive,
                "value_scalar": b.value_scalar,
                "value_rule": (
                    _child_spec_digest(b.value_rule_id, seen, en_cours)
                    if b.value_rule_id else None
                ),
            }
            for b in rule.branches
        ]

    if getattr(rule, "evaluation_order", ""):
        # Pour une NormativeFunction, l'ordre d'évaluation dit COMMENT la règle
        # s'insère dans un calcul. Le changer change son applicabilité.
        payload["evaluation_order"] = rule.evaluation_order

    return payload


def _child_spec_digest(
    rule_id: str, seen: dict[str, Digest], en_cours: set[str]
) -> Digest:
    """Empreinte de spécification d'une règle interne, avec garde de cycle.

    ``en_cours`` est passé en PARAMÈTRE et non porté par le module. Un ensemble
    global aurait été muté pendant le calcul — restauré par un ``finally``,
    donc nul en net, mais la canonicalisation doit être pure et pas seulement
    pure en apparence. Un état global n'est en outre pas réentrant : deux
    calculs concurrents se seraient marchés dessus.
    """
    from .rules import get_rule

    if rule_id in seen:
        return seen[rule_id]
    if rule_id in en_cours:
        raise UnresolvableDependency(
            f"cycle de dépendances de règles sur '{rule_id}'. Une règle ne "
            "peut pas dépendre d'elle-même, directement ou non."
        )
    d = digest_of(_spec_payload(get_rule(rule_id), seen, en_cours | {rule_id}))
    seen[rule_id] = d
    return d


def normative_spec_digest(rule: Any) -> Digest:
    """*Quelle règle* — sans une ligne de code, sans une page de preuve."""
    return digest_of(_spec_payload(rule, {}, frozenset()))


# ---------------------------------------------------------------------------
# 2. Empreinte d'implémentation, avec fermeture transitive
# ---------------------------------------------------------------------------
#: Symboles externes autorisés, un par un — et non des modules entiers.
#:
#: « math, builtins, pint » était trop large : autoriser tout ``builtins``
#: laissait entrer ``open``, ``__import__``, ``setattr``, toutes choses qui
#: n'ont rien à faire dans une règle normative et qu'une empreinte de module
#: aurait couvertes sans rien dire.
#:
#: La liste ne contient que ce que les implémentations utilisent RÉELLEMENT.
#: Y ajouter un symbole est une décision : elle élargit ce qu'une règle a le
#: droit d'appeler, et un test verrouille la liste pour que l'élargissement
#: soit délibéré.
ALLOWED_EXTERNAL_SYMBOLS: frozenset[str] = frozenset({
    "math.sqrt",        # 9.5N: la racine de f_ck
    "math.tan",         # 9.6N: cot(alpha) = 1/tan(alpha)
    "builtins.float",   # conversions explicites de magnitude
    "builtins.min",     # 9.8N et le plafond de cot(theta)_max
    "pint.Quantity",    # construction d'une grandeur avec son unité
})

#: Symboles autorises dans le NOYAU generique — notre propre code, audite,
#: dont le travail est de valider et de refuser plutot que de calculer.
#:
#: Liste INDEPENDANTE de la precedente, et non son sur-ensemble. Les deux
#: repondent a deux questions differentes — « qu'une formule d'Eurocode a le
#: droit d'appeler » et « ce que le moteur d'evaluation a le droit d'appeler »
#: — et les chainer faisait entrer `math.sqrt` dans le noyau, qui ne calcule
#: aucune racine, comme cela faisait entrer `sorted` dans le domaine d'une
#: regle, qui ne trie rien.
#:
#: Contenu exactement egal a ce que le noyau utilise: un test l'impose dans les
#: deux sens. `_autoriser` interdit d'utiliser un symbole non declare;
#: `test_aucun_symbole_declare_n_est_inutilise` interdit d'en declarer un qui
#: ne sert pas. Une entree morte est un elargissement latent — c'est ainsi que
#: `builtins.getattr` avait fini ici, alors que `_free_names` refuse de toute
#: facon tout appel a `getattr`, dont la cible n'est pas determinable.
KERNEL_ALLOWED_SYMBOLS: frozenset[str] = frozenset({
    "builtins.dict",        # construction du dictionnaire d'entrees validees
    "builtins.float",       # magnitudes explicites
    "builtins.isinstance",  # controle de type des entrees
    "builtins.set",         # comparaison des noms d'entrees attendus/recus
    "builtins.sorted",      # ordre stable des noms dans les messages de refus
    "builtins.str",         # nom d'unite vers dimension
    "pint.Quantity",        # construction d'une grandeur avec son unite
})

#: Exceptions autorisees. Elles ne calculent rien: elles REFUSENT. Leur
#: identite entre quand meme au payload — lever ValueError la ou l'on levait
#: TypeError change le comportement observable de l'appelant.
#:
#: Meme regle de non-redondance que ci-dessus. `ValueError`, `OSError` et
#: `Exception` y figuraient sans qu'aucune fonction couverte ne les emploie.
ALLOWED_EXCEPTIONS: frozenset[str] = frozenset({
    "builtins.TypeError",   # entree absente, de mauvais type ou sans unite
    "builtins.KeyError",    # regle ou implementation non enregistree
})

#: Modules dont on accepte de citer la VERSION sans parcourir le contenu.
#: Distinct de la liste ci-dessus : celle-ci dit quels symboles sont
#: appelables, celui-là d'où vient le numéro de version qui entre au payload.
_VERSIONED_ROOTS: frozenset[str] = frozenset({"math", "builtins", "pint"})

_OUR_PACKAGE = "eurostruct_engine"


def _strip_docstring(node: ast.AST) -> ast.AST:
    """Retirer le docstring : la prose n'a aucun effet sur le calcul."""
    body = getattr(node, "body", None)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        node.body = body[1:]  # type: ignore[attr-defined]
    return node


def _function_ast(fn: FunctionType) -> ast.AST:
    try:
        src = textwrap.dedent(inspect.getsource(fn))
    except (OSError, TypeError) as exc:
        # Fonction compilee a la volee, ou module dont le fichier a disparu.
        # Sans source il n'y a pas d'AST, donc rien a decrire: refus EXPLICITE
        # plutot qu'un OSError qui remonte a l'appelant comme une panne
        # technique. Sceller une boite dont on n'a pas regarde l'interieur est
        # exactement ce que la methode interdit.
        raise UnresolvableDependency(
            f"{getattr(fn, '__qualname__', fn)}: source Python indisponible "
            f"({exc}). Aucune empreinte ne peut couvrir un code qu'on ne peut "
            "pas lire."
        ) from exc
    tree = ast.parse(src)
    func = tree.body[0]
    # Les commentaires ne sont pas dans l'AST: un reformatage ou une
    # correction de commentaire ne change donc pas l'empreinte, alors qu'un
    # changement de constante ou d'opération la change.
    return _strip_docstring(func)


def _annotation_nodes(node: ast.AST) -> set[int]:
    """Identités des nœuds qui appartiennent à une annotation de type.

    Une annotation n'est pas un calcul : ``-> bool`` ne coerce rien et
    ``x: float`` ne convertit rien. Elle reste capturée mot pour mot dans le
    dump AST — la changer change donc bien l'empreinte — mais ce n'est pas une
    **dépendance appelable**, et la résoudre comme telle aurait obligé à
    inscrire ``builtins.bool`` parmi les symboles qu'une règle normative a le
    droit d'appeler. Écrire ``bool(x)`` et écrire ``-> bool`` sont deux choses
    différentes ; la liste blanche ne doit couvrir que la première.

    Les **valeurs par défaut**, elles, sont évaluées et affectent le calcul :
    elles ne sont pas exclues.
    """
    cibles: list[ast.AST] = []
    retour = getattr(node, "returns", None)
    if retour is not None:
        cibles.append(retour)
    for sub in ast.walk(node):
        if isinstance(sub, ast.arg) and sub.annotation is not None:
            cibles.append(sub.annotation)
        elif isinstance(sub, ast.AnnAssign) and sub.annotation is not None:
            cibles.append(sub.annotation)
        elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if sub is not node and sub.returns is not None:
                cibles.append(sub.returns)

    ids: set[int] = set()
    for c in cibles:
        for n in ast.walk(c):
            ids.add(id(n))
    return ids


def _free_names(node: ast.AST, fn: FunctionType) -> set[str]:
    """Noms que la fonction lit sans les définir — ses dépendances globales."""
    bound: set[str] = set()
    used: set[str] = set()

    func = node  # ast.FunctionDef

    # Tout parametre, a n'importe quelle profondeur — y compris ceux d'une
    # fonction imbriquee ou d'un lambda. Les traiter comme globaux revenait a
    # les resoudre depuis `fn.__globals__`, ce qui n'est pas seulement un refus
    # de trop: un parametre nomme `min` aurait ete resolu en `builtins.min` et
    # inscrit au payload comme une dependance que le code n'a jamais lue.
    # Distinguer deux facons d'etre « lie »:
    #   - par une DEFINITION imbriquee: le code est dans l'AST, donc sous
    #     empreinte, et l'appeler est sans danger;
    #   - par une VALEUR (parametre, affectation, `except ... as`): ce qui sera
    #     appele n'est connu qu'a l'execution.
    # Appeler un nom du second groupe est un appel indirect, refuse plus bas.
    definis: set[str] = set()
    valeurs: set[str] = set()

    # L'UNIQUE appel indirect legitime: la resolution d'une liaison, `fn =
    # _IMPLEMENTATIONS[rule_id]` puis `fn(...)`. C'est le mecanisme de dispatch
    # du moteur, et il est deja couvert par ailleurs — le registre figure au
    # payload comme `binding_registry`, la liaison rule_id -> fonction est
    # inscrite par le decorateur, et la fonction visee a sa propre empreinte.
    #
    # L'exemption est reconnue sur la FORME de l'affectation, et seulement
    # depuis un registre nomme dans `_BINDING_REGISTRIES`: n'importe quel autre
    # `f = quelque_chose[...]` suivi de `f(...)` reste refuse.
    par_registre: set[str] = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Assign) or not isinstance(sub.value, ast.Subscript):
            continue
        source = sub.value.value
        if isinstance(source, ast.Name) and source.id in _BINDING_REGISTRIES:
            for cible in sub.targets:
                if isinstance(cible, ast.Name):
                    par_registre.add(cible.id)

    for sub in ast.walk(node):
        if isinstance(sub, ast.arg):
            bound.add(sub.arg)
            valeurs.add(sub.arg)
        elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if sub is not func:
                # `implementation` retourne son `decorate` imbrique: le nom est
                # lie par la definition, pas lu depuis les globales.
                bound.add(sub.name)
                definis.add(sub.name)
        elif isinstance(sub, ast.ExceptHandler) and sub.name:
            bound.add(sub.name)
            valeurs.add(sub.name)
        elif isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
            bound.add(sub.id)
            valeurs.add(sub.id)
        elif isinstance(sub, (ast.Global, ast.Nonlocal)):
            raise UnresolvableDependency(
                f"{fn.__qualname__}: declaration '"
                f"{'global' if isinstance(sub, ast.Global) else 'nonlocal'}'. "
                "Une implementation normative ne reaffecte pas d'etat exterieur."
            )

    # Les decorateurs sont traites a part (voir _closure): ils sont enregistres
    # par leur identite ET leur propre AST, sans qu'on descende dans leurs noms
    # libres. `implementation` ne fait qu'inscrire la fonction dans un registre
    # et la rend inchangee — y descendre embarquait le registre lui-meme, un
    # dictionnaire mutable qui n'a rien a faire dans l'empreinte d'un calcul.
    #
    # Un decorateur qui ENVELOPPERAIT la fonction, lui, changerait son propre
    # AST: la propriete recherchee est donc conservee sans le bruit.
    #
    # L'exclusion se fait par IDENTITE de noeud, pas par nom: exclure « tout
    # Name nomme `implementation` » aurait aussi fait disparaitre une variable
    # locale homonyme du corps.
    ignores: set[int] = _annotation_nodes(node)
    for deco in getattr(func, "decorator_list", []):
        for n in ast.walk(deco):
            ignores.add(id(n))

    for sub in ast.walk(node):
        if id(sub) in ignores:
            continue
        if isinstance(sub, ast.Name):
            if isinstance(sub.ctx, (ast.Store, ast.Del)):
                bound.add(sub.id)
            else:
                used.add(sub.id)
        elif isinstance(sub, (ast.Import, ast.ImportFrom)):
            raise UnresolvableDependency(
                f"{fn.__qualname__}: import à l'intérieur d'une implémentation. "
                "La fermeture ne peut pas garantir ce qui sera importé à "
                "l'exécution."
            )
        elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
            if sub.func.id in ("getattr", "globals", "locals", "vars",
                               "eval", "exec", "compile", "__import__"):
                raise UnresolvableDependency(
                    f"{fn.__qualname__}: appel à '{sub.func.id}', dont la cible "
                    "n'est pas déterminable statiquement. La fermeture serait "
                    "incomplète et l'empreinte mensongère."
                )
            # Appel indirect: le nom appele designe une VALEUR — un parametre,
            # une affectation — et non une definition presente dans l'AST. Ce
            # qui s'executera n'est connu qu'a l'execution.
            #
            # Ce trou etait silencieux, et c'est le pire des deux: `f = math.sqrt`
            # suivi de `f(x)` n'inscrivait aucun symbole externe et ne passait
            # par aucun controle de liste blanche, alors qu'un `math.sqrt(x)`
            # ecrit directement y passe.
            if (sub.func.id in valeurs and sub.func.id not in definis
                    and sub.func.id not in par_registre):
                raise UnresolvableDependency(
                    f"{fn.__qualname__}: appel indirect '{sub.func.id}(...)'. "
                    "Ce nom porte une valeur, pas une definition visible dans "
                    "l'AST: la fermeture ne peut pas dire quel code s'executera."
                )
    return used - bound


def _resolve(name: str, fn: FunctionType) -> Any:
    g = fn.__globals__
    if name in g:
        return g[name]
    import builtins

    if hasattr(builtins, name):
        return getattr(builtins, name)
    raise UnresolvableDependency(
        f"{fn.__qualname__}: nom global '{name}' introuvable. La fermeture ne "
        "peut pas couvrir ce qu'elle ne résout pas."
    )


def _external_version(module_name: str) -> str:
    """Version d'une dependance de la frontiere externe.

    Un module de la bibliotheque standard n'a pas de version propre: c'est
    celle de l'interpreteur qui compte, et « inconnue » dans une piste d'audit
    ne vaut rien.
    """
    import sys

    if module_name in sys.stdlib_module_names or module_name == "builtins":
        return f"python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    try:
        from importlib.metadata import version

        return version(module_name)
    except Exception:
        mod = __import__(module_name)
        return getattr(mod, "__version__", "inconnue")


def _qualified(obj: Any, nom: str) -> str:
    """Nom pleinement qualifie d'un symbole externe, pour la liste blanche."""
    mod = getattr(obj, "__module__", None)
    if mod is None and isinstance(obj, ModuleType):
        return obj.__name__
    if mod is None:
        mod = type(obj).__module__
    racine = (mod or "").split(".")[0]
    propre = getattr(obj, "__name__", None) or type(obj).__name__
    if racine == "pint":
        # Q_ est une instance appelable liee au registre; c'est le TYPE qui
        # identifie ce qu'elle construit.
        return "pint.Quantity"
    return f"{racine}.{propre}"


def _autoriser(qualifie: str, contexte: str, autorises: frozenset[str]) -> None:
    if qualifie in ALLOWED_EXCEPTIONS:
        return
    if qualifie not in autorises:
        raise UnresolvableDependency(
            f"{contexte}: symbole externe '{qualifie}' non autorise. "
            f"Autorises: {sorted(autorises)}. "
            "Elargir cette liste est une decision: elle dit ce qu'une regle "
            "normative a le droit d'appeler."
        )


def _closure(
    fn: FunctionType, out: list[dict[str, Any]], seen: set[str],
    autorises: frozenset[str] | None = None,
) -> None:
    # Resolu ICI et non en valeur par defaut: une valeur par defaut est liee a
    # l'import, si bien que redefinir ALLOWED_EXTERNAL_SYMBOLS changeait ce que
    # le payload DECLARE sans changer ce qui est APPLIQUE. Une liste blanche
    # dont l'annonce et l'application peuvent diverger ne garantit rien.
    if autorises is None:
        autorises = ALLOWED_EXTERNAL_SYMBOLS
    key = f"{fn.__module__}.{fn.__qualname__}"
    if key in seen:
        return
    seen.add(key)

    node = _function_ast(fn)

    # --- decorateurs: politique STRICTE ------------------------------------
    decorateurs = []
    for deco in getattr(node, "decorator_list", []):
        cible = deco.func if isinstance(deco, ast.Call) else deco
        nom = getattr(cible, "id", None) or getattr(cible, "attr", None)
        if nom is None:
            raise UnresolvableDependency(
                f"{key}: decorateur dont la cible n'est pas un nom simple."
            )
        obj = fn.__globals__.get(nom)

        # Un decorateur doit etre une fonction DE NOTRE PAQUET. Sinon: refus.
        # Aucun traitement superficiel n'est applique par defaut, meme a un
        # decorateur d'identite exterieur parfaitement inoffensif — la
        # fermeture ne le sait pas, et « inoffensif » ne se suppose pas.
        if (not isinstance(obj, FunctionType)
                or (obj.__module__ or "").split(".")[0] != _OUR_PACKAGE):
            raise UnresolvableDependency(
                f"{key}: decorateur '{nom}' inconnu. Un decorateur doit etre "
                "une fonction de notre paquet, dont la fermeture transitive "
                "est entierement resolue. Aucun traitement superficiel n'est "
                "applique par defaut, et le canonicaliseur ne l'EXECUTE jamais "
                "pour en decider."
            )

        entree: dict[str, Any] = {
            "decorator": f"{obj.__module__}.{obj.__qualname__}",
        }

        if nom in _KNOWN_IDENTITY_DECORATORS:
            # Preuve STATIQUE, sur l'AST, sans appeler le decorateur. La sonde
            # qui l'executait est supprimee: calculer une empreinte ne doit
            # produire aucun effet de bord ni executer de code applicatif.
            #
            # La preuve passe AVANT la fermeture: elle est la precondition du
            # traitement particulier. Resoudre d'abord la fermeture faisait
            # refuser un decorateur enveloppant pour son appel indirect
            # `fn(...)` — un refus juste, mais qui masquait la vraie raison et
            # aurait laisse passer une rupture d'identite sans appel indirect.
            entree["identity_proof"] = _preuve_identite_statique(obj)
            args = [
                ast.literal_eval(a) for a in getattr(deco, "args", [])
                if isinstance(a, ast.Constant)
            ]
            entree["arguments"] = args
            entree["binding"] = {"rule_id": args[0] if args else None,
                                 "function": key}

        # Sa fermeture, comme celle de n'importe laquelle de nos fonctions:
        # son AST et ses dependances entrent au payload, si bien que toute
        # modification du decorateur change l'empreinte. Un `seen` PROPRE, pour
        # que l'entree soit auto-suffisante et ne depende pas de ce qui a deja
        # ete parcouru par ailleurs.
        sous: list[dict[str, Any]] = []
        _closure(obj, sous, set(), autorises)
        entree["closure"] = sous

        decorateurs.append(entree)

    out.append({
        "function": key,
        "ast": ast.dump(node, include_attributes=False),
        "decorators": decorateurs,
    })

    # --- dependances -------------------------------------------------------
    for nom in sorted(_free_names(node, fn)):
        obj = _resolve(nom, fn)

        if isinstance(obj, ModuleType):
            racine = obj.__name__.split(".")[0]
            if racine == _OUR_PACKAGE:
                out.append({"module": obj.__name__, "version": "interne"})
                continue
            if racine in _VERSIONED_ROOTS:
                # Le module seul ne dit rien: ce sont les SYMBOLES appeles qui
                # comptent, et ils sont verifies ci-dessous a l'usage.
                out.append({"module": obj.__name__,
                            "version": _external_version(racine)})
                continue
            raise UnresolvableDependency(
                f"{key}: module '{obj.__name__}' hors des racines versionnees "
                f"{sorted(_VERSIONED_ROOTS)}."
            )

        if isinstance(obj, FunctionType):
            if (obj.__module__ or "").split(".")[0] == _OUR_PACKAGE:
                _closure(obj, out, seen, autorises)
                continue
            q = _qualified(obj, nom)
            _autoriser(q, key, autorises)
            out.append({"external_symbol": q,
                        "version": _external_version(q.split(".")[0])})
            continue

        if isinstance(obj, (int, float, str, bool, tuple, frozenset)) or obj is None:
            out.append({"constant": nom, "value": obj})
            continue

        # Le registre de liaison rule_id -> fonction. C'est le mecanisme qui
        # resout la liaison posee par le decorateur `implementation`, et il
        # doit figurer dans le noyau. On enregistre son IDENTITE, jamais son
        # contenu vivant: y mettre les cles ferait dependre l'empreinte de
        # chaque regle de toutes les autres regles enregistrees.
        #
        # La liaison PROPRE a la regle est deja portee par son decorateur, et
        # le comportement de la resolution est dans l'AST ci-dessus. Ce
        # traitement vaut pour CE registre nomme et pour aucun autre
        # dictionnaire: tout autre etat mutable global reste refuse.
        if nom in _BINDING_REGISTRIES and isinstance(obj, dict):
            out.append({
                "binding_registry": f"{fn.__module__}.{nom}",
                "resolves": _BINDING_REGISTRIES[nom],
            })
            continue

        _mod = (getattr(obj, "__module__", "") or "").split(".")[0]
        if _mod in ("typing", "collections", "abc", "types"):
            out.append({
                "typing_construct":
                    f"{_mod}.{getattr(obj, '_name', None) or getattr(obj, '__name__', repr(obj))}"
            })
            continue

        # Nos propres classes — exceptions comprises. Elles ne sont pas
        # « externes »: leur identite suffit, et changer l'exception levee
        # change bien le comportement observable, donc l'empreinte.
        if isinstance(obj, type) and (obj.__module__ or "").split(".")[0] == _OUR_PACKAGE:
            out.append({"internal_class": f"{obj.__module__}.{obj.__qualname__}"})
            continue

        if callable(obj):
            q = _qualified(obj, nom)
            _autoriser(q, key, autorises)
            out.append({"external_symbol": q,
                        "version": _external_version(q.split(".")[0])})
            continue

        raise UnresolvableDependency(
            f"{key}: dependance '{nom}' de type {type(obj).__name__}, que la "
            "fermeture ne sait pas decrire. Refus explicite: une empreinte "
            "incomplete est pire qu'absente."
        )

    # --- appels a des symboles externes par attribut (math.sqrt, ...) -------
    #
    # Ces appels etaient VERIFIES contre la liste blanche mais pas INSCRITS: le
    # payload nommait le module et sa version, jamais le symbole appele. La
    # difference se voyait a l'inventaire — `math.sqrt` et `math.tan`, pourtant
    # utilises par rho_w_min et s_l_max, apparaissaient comme « declares mais
    # non utilises ». On les inscrit donc au meme titre qu'un appel direct.
    vus_attr: list[str] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            base = sub.func.value
            if isinstance(base, ast.Name):
                obj = fn.__globals__.get(base.id)
                if isinstance(obj, ModuleType):
                    racine = obj.__name__.split(".")[0]
                    if racine != _OUR_PACKAGE:
                        q = f"{racine}.{sub.func.attr}"
                        _autoriser(q, key, autorises)
                        if q not in vus_attr:
                            vus_attr.append(q)
                            out.append({"external_symbol": q,
                                        "version": _external_version(racine)})


#: Version de la preuve d'identite. Elle entre au payload: durcir ou assouplir
#: la preuve change ce qu'une empreinte atteste, donc l'empreinte elle-meme.
IDENTITY_PROOF_VERSION = "esc-identity/1"


def _portee_propre(node: ast.AST) -> list[ast.AST]:
    """Nœuds de la portée **propre** d'une fonction.

    Ne descend pas dans les définitions imbriquées : leurs ``return`` sont
    ceux d'une autre fonction et n'ont rien à dire sur celle-ci.
    """
    trouves: list[ast.AST] = []
    pile: list[ast.AST] = list(getattr(node, "body", []))
    while pile:
        n = pile.pop()
        trouves.append(n)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda,
                          ast.ClassDef)):
            continue
        pile.extend(ast.iter_child_nodes(n))
    return trouves


def _termine_par(corps: list[ast.stmt], nom: str) -> bool:
    """Toute voie de sortie de *corps* rend-elle ``nom``, ou lève-t-elle ?

    Conservateur par construction : une forme non reconnue répond ``False``,
    donc refus. Mieux vaut refuser un décorateur écrit autrement que prouver
    à tort qu'il rend la fonction reçue.
    """
    if not corps:
        return False
    dernier = corps[-1]
    if isinstance(dernier, ast.Return):
        return isinstance(dernier.value, ast.Name) and dernier.value.id == nom
    if isinstance(dernier, ast.Raise):
        return True
    if isinstance(dernier, ast.If):
        return (bool(dernier.orelse)
                and _termine_par(dernier.body, nom)
                and _termine_par(dernier.orelse, nom))
    return False


def _rend_exactement(func: ast.AST, nom: str, quoi: str) -> None:
    """Prouver statiquement que *func* rend l'objet lié à *nom*, ou lever.

    Trois conditions, toutes nécessaires :

    1. **aucun `return` ne rend autre chose** — un seul ``return emballage``
       suffit à ruiner la propriété ;
    2. **`nom` n'est jamais réaffecté** — sinon ``fn = enveloppe(fn)`` puis
       ``return fn`` passerait la condition 1 en rendant un autre objet ;
    3. **toute voie de sortie termine** par ce ``return`` ou par un ``raise``
       — une chute en fin de corps rendrait ``None``.
    """
    portee = _portee_propre(func)

    for n in portee:
        if isinstance(n, ast.Name) and n.id == nom and isinstance(
            n.ctx, (ast.Store, ast.Del)
        ):
            raise UnresolvableDependency(
                f"{quoi}: '{nom}' est reaffecte. Rendre '{nom}' apres l'avoir "
                "remplace n'est pas rendre ce qui a ete recu."
            )

    for n in portee:
        if isinstance(n, ast.Return):
            if not (isinstance(n.value, ast.Name) and n.value.id == nom):
                raise UnresolvableDependency(
                    f"{quoi}: une voie de retour ne rend pas '{nom}'. Le "
                    "contrat d'identite n'est pas etabli."
                )

    if not _termine_par(getattr(func, "body", []), nom):
        raise UnresolvableDependency(
            f"{quoi}: les voies de sortie ne se terminent pas toutes par "
            f"`return {nom}` ou par un `raise`. Une chute en fin de corps "
            "rendrait None."
        )


def _preuve_identite_statique(deco: FunctionType) -> str:
    """Prouver, **sans l'exécuter**, que *deco* rend la fonction qu'il reçoit.

    Remplace la sonde qui appelait réellement le décorateur. Cette sonde avait
    deux défauts, et le second est rédhibitoire pour une canonicalisation :

    - elle avait un **effet de bord** — ``implementation`` inscrivait la sonde
      dans ``_IMPLEMENTATIONS`` — que seule une restauration explicite des
      registres déclarés annulait. Un effet de bord ailleurs n'aurait pas été
      annulé ;
    - calculer une empreinte **exécutait du code applicatif**. Une empreinte
      décrit ; elle ne doit rien faire arriver.

    Deux formes sont reconnues, toutes deux conservatrices :

    ``direct``
        ``def deco(fn): ...; return fn``

    ``fabrique``
        ``def deco(arg): def interne(fn): ...; return fn; return interne`` —
        la forme d'``implementation``.

    Toute autre écriture est **refusée**, y compris si elle serait correcte :
    une preuve conservatrice qui refuse trop est un obstacle visible, une
    preuve trop permissive est une fausse garantie.
    """
    quoi = f"{deco.__module__}.{deco.__qualname__}"
    node = _function_ast(deco)

    if getattr(node, "decorator_list", []):
        raise UnresolvableDependency(
            f"{quoi}: decorateur lui-meme decore. La preuve d'identite ne "
            "couvre pas cette composition."
        )

    imbriquees = [
        n for n in _portee_propre(node)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    if not imbriquees:
        # Forme directe: l'unique parametre est la fonction decoree.
        parametres = _parametre_unique(node, quoi)
        _rend_exactement(node, parametres, quoi)
        return f"{IDENTITY_PROOF_VERSION}/direct"

    if len(imbriquees) != 1:
        raise UnresolvableDependency(
            f"{quoi}: {len(imbriquees)} definitions imbriquees. La preuve "
            "n'est etablie que pour une fabrique a un seul decorateur interne."
        )

    interne = imbriquees[0]
    if interne.decorator_list:
        raise UnresolvableDependency(
            f"{quoi}: le decorateur interne '{interne.name}' est lui-meme "
            "decore."
        )

    # La fabrique doit rendre EXACTEMENT sa fonction interne...
    _rend_exactement(node, interne.name, f"{quoi} (fabrique)")
    # ... et cette fonction interne doit rendre EXACTEMENT son parametre.
    _rend_exactement(
        interne, _parametre_unique(interne, f"{quoi}.{interne.name}"),
        f"{quoi}.{interne.name}",
    )
    return f"{IDENTITY_PROOF_VERSION}/fabrique"


def _parametre_unique(func: ast.AST, quoi: str) -> str:
    """Le nom du paramètre qui reçoit la fonction décorée.

    Exiger qu'il soit unique n'est pas cosmétique : un décorateur à plusieurs
    paramètres pourrait rendre l'un ou l'autre, et la preuve devrait alors
    déterminer lequel porte la fonction — ce qu'elle ne sait pas faire.
    """
    args = func.args  # type: ignore[attr-defined]
    positionnels = list(args.posonlyargs) + list(args.args)
    if (len(positionnels) != 1 or args.vararg or args.kwarg
            or args.kwonlyargs or args.defaults):
        raise UnresolvableDependency(
            f"{quoi}: le contrat d'identite exige exactement un parametre "
            "positionnel, sans valeur par defaut ni parametre variadique."
        )
    return positionnels[0].arg


#: Les DEUX registres de liaison du moteur, nommes un par un. Ils resolvent
#: ce que le decorateur a pose; leur identite entre au payload, jamais leur
#: contenu vivant. Tout autre dictionnaire global reste refuse.
_BINDING_REGISTRIES: dict[str, str] = {
    "_IMPLEMENTATIONS": "rule_id -> fonction qualifiee",
    "_RULES": "rule_id -> declaration de regle",
}

#: Decorateurs dont l'identite a ete VERIFIEE et qui recoivent le traitement
#: par liaison. Tout le reste doit voir sa fermeture resolue ou etre refuse.
_KNOWN_IDENTITY_DECORATORS: frozenset[str] = frozenset({"implementation"})


def _dedoublonne(fragments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dedoublonnage a ORDRE PRESERVE des fragments d'une fermeture.

    Deux appels a Q_ dans une meme fonction, ou deux fonctions du noyau lisant
    le meme registre de liaison, produisent des fragments identiques. Sans
    consequence sur la stabilite — l'ordre est deterministe — mais le payload
    doit rester lisible par un humain dans dix ans, et un doublon inexplique
    lui coute du temps.
    """
    vus: list[str] = []
    uniques: list[dict[str, Any]] = []
    for f in fragments:
        cle = canonical_json(f)
        if cle not in vus:
            vus.append(cle)
            uniques.append(f)
    return uniques


# ---------------------------------------------------------------------------
# Noyau generique d'evaluation
# ---------------------------------------------------------------------------
def _kernel_functions(rule_type: Any) -> tuple[Any, ...]:
    """Le code GENERIQUE qui execute une regle de ce type.

    Les empreintes d'implementation ne couvraient que la mathematique propre a
    chaque regle. Or ``alpha_cw`` n'a AUCUN code propre: tout ce qu'elle fait
    — choisir une branche, appliquer les inclusivites, verifier le domaine,
    resoudre une regle interne, convertir les unites — vit dans ce noyau. Le
    modifier changeait son resultat sans changer son empreinte.
    """
    from ..units import require_dimension
    from .rules import (
        Branch,
        ConditionalRule,
        DomainBound,
        FormulaRule,
        NormativeFunction,
        NormativeRule,
        RuleKind,
        ScalarRule,
        _dim_of,
        get_rule,
        implementation,
    )

    commun = (
        NormativeRule._validate_inputs,   # presence, unites, domaine
        require_dimension,                # controle dimensionnel
        DomainBound.check,                # bornes, inclusivites, bornes relatives
    )
    # `implementation` figure aupres des deux types dont l'`evaluate` va
    # CHERCHER une mathematique dans `_IMPLEMENTATIONS`: c'est l'autre moitie
    # du mecanisme de liaison pose par le decorateur, et une liaison n'est
    # verifiable que si ses deux moities sont sous empreinte. ScalarRule n'en a
    # pas besoin (sa valeur est une donnee) et ConditionalRule non plus (elle
    # delegue a des regles filles, dont les empreintes propres le couvrent).
    par_type = {
        RuleKind.SCALAR: (ScalarRule.evaluate,),
        RuleKind.FORMULA: (FormulaRule.evaluate, _dim_of, implementation),
        RuleKind.CONDITIONAL_RULE: (
            ConditionalRule.evaluate, Branch.contains, get_rule,
        ),
        RuleKind.FUNCTION: (NormativeFunction.evaluate, _dim_of, implementation),
    }
    return commun + par_type[rule_type]


def evaluation_kernel_digest(rule_type: Any) -> Digest:
    """Empreinte du chemin generique d'evaluation, par type de regle.

    Incluse dans chaque ``implementation_digest``: si le selecteur de branche,
    le controle des bornes ou la conversion d'unites change de comportement,
    l'empreinte de la regle change.
    """
    fragments: list[dict[str, Any]] = []
    seen: set[str] = set()
    for f in _kernel_functions(rule_type):
        cible = getattr(f, "__func__", f)
        _closure(cible, fragments, seen, KERNEL_ALLOWED_SYMBOLS)
    return digest_of({
        "kind": "evaluation_kernel",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "rule_type": rule_type.value,
        "closure": _dedoublonne(fragments),
        "allowed_external_symbols": sorted(ALLOWED_EXTERNAL_SYMBOLS),
    })


def implementation_digest(rule: Any) -> Digest:
    """*Quel code exécute cette règle*, avec la fermeture de ses dépendances.

    Couvre transitivement : l'AST du corps, les constantes de module lues, les
    fonctions auxiliaires de notre paquet, et les **règles internes** via leur
    propre empreinte d'implémentation.

    Lève :class:`UnresolvableDependency` plutôt que de produire une empreinte
    partielle. Voir :data:`ALLOWED_EXTERNAL_SYMBOLS` pour la liste, symbole
    par symbole, de ce qu'une règle a le droit d'appeler hors de notre code.
    """
    from .rules import (
        _IMPLEMENTATIONS,
        ConditionalRule,
        ScalarRule,
        get_rule,
    )

    fragments: list[dict[str, Any]] = []
    seen: set[str] = set()

    fn = _IMPLEMENTATIONS.get(rule.rule_id)
    if fn is not None:
        _closure(fn, fragments, seen)
    elif not isinstance(rule, (ScalarRule, ConditionalRule)):
        raise UnresolvableDependency(
            f"{rule.rule_id}: aucune implémentation enregistrée, et ce type de "
            "règle en exige une."
        )

    children: list[Digest] = []
    if isinstance(rule, ConditionalRule):
        children.append(implementation_digest(get_rule(rule.selector_rule_id)))
        for b in rule.branches:
            if b.value_rule_id:
                children.append(implementation_digest(get_rule(b.value_rule_id)))

    fragments = _dedoublonne(fragments)

    return digest_of({
        "kind": "implementation",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "rule_id": rule.rule_id,
        "closure": fragments,
        "internal_rules": children,
        # Le noyau generique: sans lui, alpha_cw — qui n'a aucun code propre —
        # aurait une empreinte insensible a tout changement du selecteur de
        # branche ou du controle des bornes.
        "evaluation_kernel": evaluation_kernel_digest(rule.rule_type),
        "allowed_external_symbols": sorted(ALLOWED_EXTERNAL_SYMBOLS),
    })


# ---------------------------------------------------------------------------
# 3. Empreinte de preuve
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """Un document ouvert, à une page, avec ce qui y a été lu.

    Remplace ``pages_read: tuple[int, ...]``, ambigu dès que plusieurs
    documents interviennent — et ils interviennent toujours : base, corrigenda,
    amendement, annexe.
    """

    document_digest: str
    document_role: str          # base | corrigendum | amendement | annexe | reglement
    reference: str
    edition: str
    clause: str
    page_printed: int
    quote: str
    page_pdf: int | None = None


def evidence_digest(items: tuple[EvidenceItem, ...]) -> Digest:
    """*Ce que le vérificateur atteste avoir lu.*

    ``page_pdf`` est conservé comme aide de navigation mais **exclu de
    l'empreinte** : ce n'est pas une autorité normative, et il change avec le
    tirage du fichier. Le folio imprimé, lui, est ce qu'un ingénieur rouvre.
    """
    return digest_of({
        "kind": "evidence",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "items": [
            {
                "document_digest": i.document_digest,
                "document_role": i.document_role,
                "reference": i.reference,
                "edition": i.edition,
                "clause": i.clause,
                "page_printed": i.page_printed,
                "quote": i.quote,
                "quote_digest": hashlib.sha256(i.quote.encode("utf-8")).hexdigest(),
            }
            for i in items
        ],
    })
