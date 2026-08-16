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
import json
import textwrap
from dataclasses import dataclass
from types import BuiltinFunctionType, FunctionType, ModuleType
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
    "EXTERNAL_BOUNDARY",
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
def _canonical(value: Any) -> Any:
    """Ramener une valeur à une forme dont la sérialisation est déterministe.

    Les flottants passent par ``repr``, qui donne en Python 3 la plus courte
    écriture faisant un aller-retour exact. ``json.dumps`` produirait la même
    chose ici, mais l'écrire rend la propriété explicite plutôt que héritée
    d'une bibliothèque.

    Les grandeurs Pint sont sérialisées **avec leur unité déclarée**, pas
    converties en unité de base : ``Q_(12.0, "MPa")`` et ``Q_(12000.0, "kPa")``
    sont la même grandeur physique et deux déclarations différentes. Confondre
    les deux masquerait un changement d'unité dans une borne de domaine — ce
    que l'empreinte existe précisément pour attraper.
    """
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return {"__float__": repr(value)}
    if hasattr(value, "magnitude") and hasattr(value, "units"):
        return {
            "__quantity__": {
                "magnitude": repr(float(value.magnitude)),
                "units": str(value.units),
            }
        }
    if isinstance(value, Digest):
        return {"__digest__": value.digest,
                "canonicalization_version": value.canonicalization_version}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if isinstance(value, (set, frozenset)):
        # Un ensemble n'a pas d'ordre; le tri le lui donne, sans quoi deux
        # exécutions du même programme produiraient deux empreintes.
        return sorted(_canonical(v) for v in value)
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in sorted(value.items())}
    if hasattr(value, "value") and hasattr(value, "name"):      # Enum
        return {"__enum__": f"{type(value).__name__}.{value.name}",
                "value": value.value}
    raise UnresolvableDependency(
        f"valeur non canonicalisable: {type(value).__name__}. Ajouter une "
        "règle de sérialisation explicite plutôt que de la laisser tomber "
        "dans une représentation par défaut."
    )


def canonical_json(payload: Any) -> str:
    """JSON canonique : clés triées, séparateurs fixes, pas d'échappement ASCII."""
    return json.dumps(
        _canonical(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
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
def _spec_payload(rule: Any, seen: dict[str, Digest]) -> dict[str, Any]:
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
        payload["selector"] = _child_spec_digest(rule.selector_rule_id, seen)
        payload["branches"] = [
            {
                "lower": b.lower,
                "upper": b.upper,
                "lower_inclusive": b.lower_inclusive,
                "upper_inclusive": b.upper_inclusive,
                "value_scalar": b.value_scalar,
                "value_rule": (
                    _child_spec_digest(b.value_rule_id, seen)
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


def _child_spec_digest(rule_id: str, seen: dict[str, Digest]) -> Digest:
    from .rules import get_rule

    if rule_id in seen:
        return seen[rule_id]
    if rule_id in _IN_PROGRESS:
        raise UnresolvableDependency(
            f"cycle de dépendances de règles sur '{rule_id}'. Une règle ne "
            "peut pas dépendre d'elle-même, directement ou non."
        )
    _IN_PROGRESS.add(rule_id)
    try:
        d = digest_of(_spec_payload(get_rule(rule_id), seen))
    finally:
        _IN_PROGRESS.discard(rule_id)
    seen[rule_id] = d
    return d


_IN_PROGRESS: set[str] = set()


def normative_spec_digest(rule: Any) -> Digest:
    """*Quelle règle* — sans une ligne de code, sans une page de preuve."""
    return digest_of(_spec_payload(rule, {}))


# ---------------------------------------------------------------------------
# 2. Empreinte d'implémentation, avec fermeture transitive
# ---------------------------------------------------------------------------
#: Frontière externe DÉCLARÉE. Ces modules sont hors de notre code ; leur
#: contenu n'est pas parcouru, mais leur **version** entre dans l'empreinte,
#: de sorte qu'une mise à jour de Pint ou du Python hôte ne passe pas
#: inaperçue.
#:
#: Tout ce qui n'est ni notre code ni cette liste fait lever
#: :class:`UnresolvableDependency`. La liste est courte exprès : chaque entrée
#: est une chose que l'empreinte ne surveille pas dans le détail, et cela doit
#: rester visible.
EXTERNAL_BOUNDARY: frozenset[str] = frozenset({"math", "builtins", "pint"})

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
    src = textwrap.dedent(inspect.getsource(fn))
    tree = ast.parse(src)
    func = tree.body[0]
    # Les commentaires ne sont pas dans l'AST: un reformatage ou une
    # correction de commentaire ne change donc pas l'empreinte, alors qu'un
    # changement de constante ou d'opération la change.
    return _strip_docstring(func)


def _free_names(node: ast.AST, fn: FunctionType) -> set[str]:
    """Noms que la fonction lit sans les définir — ses dépendances globales."""
    bound: set[str] = set()
    used: set[str] = set()

    func = node  # ast.FunctionDef
    args = func.args  # type: ignore[attr-defined]
    for a in (
        list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
        + ([args.vararg] if args.vararg else [])
        + ([args.kwarg] if args.kwarg else [])
    ):
        bound.add(a.arg)

    # Les decorateurs sont traites a part (voir _closure): ils sont enregistres
    # par leur identite ET leur propre AST, sans qu'on descende dans leurs noms
    # libres. `implementation` ne fait qu'inscrire la fonction dans un registre
    # et la rend inchangee — y descendre embarquait le registre lui-meme, un
    # dictionnaire mutable qui n'a rien a faire dans l'empreinte d'un calcul.
    #
    # Un decorateur qui ENVELOPPERAIT la fonction, lui, changerait son propre
    # AST: la propriete recherchee est donc conservee sans le bruit.
    decorateurs = set()
    for deco in getattr(func, "decorator_list", []):
        for n in ast.walk(deco):
            if isinstance(n, ast.Name):
                decorateurs.add(n.id)

    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in decorateurs:
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


def _closure(fn: FunctionType, out: list[dict[str, Any]], seen: set[str]) -> None:
    key = f"{fn.__module__}.{fn.__qualname__}"
    if key in seen:
        return
    seen.add(key)

    node = _function_ast(fn)
    decorateurs = []
    for deco in getattr(node, "decorator_list", []):
        cible = deco.func if isinstance(deco, ast.Call) else deco
        nom = getattr(cible, "id", None) or getattr(cible, "attr", None) or "?"
        entree = {"decorator": nom, "call_ast": ast.dump(deco, include_attributes=False)}
        obj = fn.__globals__.get(nom)
        if isinstance(obj, FunctionType) and (obj.__module__ or "").split(".")[0] == _OUR_PACKAGE:
            # L'AST du decorateur lui-meme: s'il se met a envelopper la
            # fonction, l'empreinte le voit.
            entree["decorator_ast"] = ast.dump(
                _function_ast(obj), include_attributes=False
            )
        decorateurs.append(entree)

    out.append({
        "function": key,
        "ast": ast.dump(node, include_attributes=False),
        "decorators": decorateurs,
    })

    for name in sorted(_free_names(node, fn)):
        obj = _resolve(name, fn)

        if isinstance(obj, ModuleType):
            root = obj.__name__.split(".")[0]
            if root in EXTERNAL_BOUNDARY or root == _OUR_PACKAGE:
                out.append({
                    "module": obj.__name__,
                    "version": (_external_version(root)
                                if root != _OUR_PACKAGE else "interne"),
                })
                continue
            raise UnresolvableDependency(
                f"{key}: module '{obj.__name__}' hors de la frontière déclarée "
                f"{sorted(EXTERNAL_BOUNDARY)}. Ajouter le module à la "
                "frontière est une décision, pas un détail: elle dit ce que "
                "l'empreinte ne surveille plus dans le détail."
            )

        if isinstance(obj, FunctionType):
            mod = (obj.__module__ or "").split(".")[0]
            if mod == _OUR_PACKAGE:
                _closure(obj, out, seen)          # récursion: notre code
            else:
                out.append({"external_callable": f"{obj.__module__}.{obj.__qualname__}",
                            "version": _external_version(mod)})
            continue

        if isinstance(obj, BuiltinFunctionType) or (
            callable(obj) and getattr(obj, "__module__", "").split(".")[0]
            in EXTERNAL_BOUNDARY
        ):
            mod = (getattr(obj, "__module__", "builtins") or "builtins").split(".")[0]
            out.append({
                "external_callable": f"{mod}.{getattr(obj, '__name__', repr(obj))}",
                "version": _external_version(mod),
            })
            continue

        if callable(obj) and type(obj).__module__.split(".")[0] in EXTERNAL_BOUNDARY:
            # Q_ est un objet appelable de Pint, pas une fonction.
            out.append({
                "external_callable_object": f"{type(obj).__module__}.{type(obj).__name__}",
                "version": _external_version(type(obj).__module__.split(".")[0]),
            })
            continue

        if isinstance(obj, (int, float, str, bool, tuple, frozenset)) or obj is None:
            out.append({"constant": name, "value": obj})
            continue

        # Constructions de typage. Elles apparaissent dans la fermeture parce
        # que le decorateur d'enregistrement les annote, et elles n'ont aucun
        # effet sur le calcul. On les enregistre par leur nom sans y descendre:
        # descendre dans `typing` reviendrait a hacher la bibliotheque standard.
        #
        # Une annotation modifiee changera quand meme l'empreinte, l'AST la
        # portant — faux positif de la meme famille que le renommage d'une
        # variable locale, et accepte pour la meme raison.
        _mod = (getattr(obj, "__module__", "") or "").split(".")[0]
        if _mod in ("typing", "collections", "abc", "types"):
            out.append({
                "typing_construct": f"{_mod}.{getattr(obj, '_name', None) or getattr(obj, '__name__', repr(obj))}"
            })
            continue

        raise UnresolvableDependency(
            f"{key}: dépendance '{name}' de type {type(obj).__name__}, que la "
            "fermeture ne sait pas décrire. Refus explicite: une empreinte "
            "incomplète est pire qu'absente."
        )


def implementation_digest(rule: Any) -> Digest:
    """*Quel code exécute cette règle*, avec la fermeture de ses dépendances.

    Couvre transitivement : l'AST du corps, les constantes de module lues, les
    fonctions auxiliaires de notre paquet, et les **règles internes** via leur
    propre empreinte d'implémentation.

    Lève :class:`UnresolvableDependency` plutôt que de produire une empreinte
    partielle. Voir :data:`EXTERNAL_BOUNDARY` pour ce qui est délibérément
    laissé hors du parcours détaillé — et suivi par sa version.
    """
    from .rules import ConditionalRule, ScalarRule, get_rule
    from .rules import _IMPLEMENTATIONS  # noqa: PLC2701 — accès délibéré

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

    # Dedoublonnage a ORDRE PRESERVE: deux appels a Q_ dans une meme fonction
    # produisaient deux fragments identiques. Sans consequence sur la stabilite
    # — l'ordre est deterministe — mais le payload doit rester lisible par un
    # humain dans dix ans, et un doublon inexplique lui coute du temps.
    vus: list[str] = []
    uniques: list[dict[str, Any]] = []
    for f in fragments:
        cle = canonical_json(f)
        if cle not in vus:
            vus.append(cle)
            uniques.append(f)
    fragments = uniques

    return digest_of({
        "kind": "implementation",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "rule_id": rule.rule_id,
        "closure": fragments,
        "internal_rules": children,
        "external_boundary": sorted(EXTERNAL_BOUNDARY),
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
