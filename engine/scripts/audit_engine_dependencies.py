#!/usr/bin/env python3
"""Audit the calculation engine's dependency tree — TICKET 3.1 and 6.2.

    "Interdire tout appel reseau dans le moteur de calcul.
     Interdire toute dependance IA dans la chaine numerique finale.
     Limiter le moteur aux bibliotheques strictement necessaires.
     Ajouter un controle CI sur l'arbre de dependances."

A grep over the source is not enough: a language-model client can arrive three
levels down a transitive dependency without any import appearing in our code.
So this walks the *installed distribution metadata* and checks every package
that ends up in the engine's environment.

Three checks, all blocking:

1. **Allowlist** — every transitive dependency must be explicitly listed here.
   A new package, however innocent, requires a deliberate decision.
2. **Denylist** — known AI clients, HTTP stacks and RPC frameworks are refused
   by name, so an accidental allowlist entry cannot let one through.
3. **Source scan** — no module of the engine may import a network or AI module,
   including inside a function body.

    python scripts/audit_engine_dependencies.py
"""

from __future__ import annotations

import ast
import re
import sys
from importlib.metadata import PackageNotFoundError, distribution, requires
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
SRC = ENGINE / "src" / "eurostruct_engine"

#: Everything the deterministic engine is allowed to pull in, transitively.
#: Adding a line here is a decision about what runs inside a calculation whose
#: results are signed by an engineer.
ALLOWED: dict[str, str] = {
    "eurostruct-engine": "le moteur lui-meme",
    # Direct
    "pint": "typage des unites physiques (§5.2, §8.2)",
    "pydantic": "validation stricte du contrat d'interface",
    "ezdxf": "generation DXF deterministe (§5.2)",
    "numpy": "algebre lineaire pour le MEF",
    # Transitive
    "pydantic-core": "noyau de pydantic",
    "annotated-types": "dependance de pydantic",
    "typing-extensions": "retro-portage de typing",
    "typing-inspection": "dependance de pydantic",
    "flexcache": "dependance de pint",
    "flexparser": "dependance de pint",
    "platformdirs": "dependance de pint (cache du registre d'unites)",
    "fonttools": "dependance d'ezdxf (metriques de police pour les textes DXF)",
    "pyparsing": "dependance d'ezdxf",
}

#: Refused by name whatever the allowlist says.
DENIED_PACKAGES = {
    "openai", "anthropic", "cohere", "mistralai", "google-generativeai",
    "google-genai", "langchain", "langchain-core", "llama-index", "transformers",
    "torch", "tensorflow", "sentence-transformers", "tiktoken", "litellm",
    "requests", "httpx", "httpcore", "aiohttp", "urllib3", "websockets",
    "grpcio", "boto3", "botocore", "google-cloud-storage", "azure-core",
}

#: Modules the engine source may never import — a network call is a network
#: call whether it is at module level or inside a function.
DENIED_IMPORTS = {
    "socket", "ssl", "http", "urllib", "urllib3", "requests", "httpx",
    "aiohttp", "ftplib", "telnetlib", "smtplib", "xmlrpc", "asyncio",
    "openai", "anthropic", "langchain", "transformers", "torch", "subprocess",
}

def walk_tree() -> dict[str, str]:
    """Every distribution reachable from eurostruct-engine, with its version."""
    found: dict[str, str] = {}

    def visit(name: str) -> None:
        key = name.lower().replace("_", "-")
        if key in found:
            return
        try:
            found[key] = distribution(key).version
        except PackageNotFoundError:
            return
        for raw in requires(key) or []:
            if "extra ==" in raw:          # optional extras are not installed
                continue
            dep = re.split(r"[<>=!~;\[\s]", raw.strip())[0]
            if dep:
                visit(dep)

    visit("eurostruct-engine")
    return found


def scan_imports(root: Path | None = None) -> list[tuple[Path, int, str]]:
    """Every forbidden import under *root*, including nested ones.

    Takes a root so the check itself can be exercised against a crafted
    file: a guard nobody has seen fail is not a guard.
    """
    offenders: list[tuple[Path, int, str]] = []
    for path in sorted((root or SRC).rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:                 # relative import, ours
                    continue
                names = [node.module or ""]
            for name in names:
                if name.split(".")[0] in DENIED_IMPORTS:
                    offenders.append((path, node.lineno, name))
    return offenders


def main() -> int:
    failures: list[str] = []
    tree = walk_tree()

    print("=== Arbre de dependances du moteur ===")
    for name in sorted(tree):
        note = ALLOWED.get(name, "")
        mark = " " if name in ALLOWED else "!"
        print(f" {mark} {name:<26} {tree[name]:<12} {note}")

    unexpected = sorted(set(tree) - set(ALLOWED))
    if unexpected:
        failures.append(
            "dependance(s) non autorisee(s) dans le moteur: "
            + ", ".join(unexpected)
            + ". Toute nouvelle dependance du noyau de calcul doit etre ajoutee "
            "explicitement a ALLOWED, avec sa justification."
        )

    denied = sorted(set(tree) & DENIED_PACKAGES)
    if denied:
        failures.append(
            "dependance(s) IA ou reseau presente(s) dans le moteur: "
            + ", ".join(denied)
            + ". Interdiction 1: aucune valeur de calcul ne peut provenir d'un LLM."
        )

    print("\n=== Imports du code moteur ===")
    offenders = scan_imports()
    if offenders:
        for path, line, name in offenders:
            print(f" ! {path.relative_to(ENGINE)}:{line} importe '{name}'")
        failures.append(
            f"{len(offenders)} import(s) reseau ou IA dans le code du moteur."
        )
    else:
        print(" aucun import reseau ni IA")

    print()
    if failures:
        for f in failures:
            print(f"::error::{f}", file=sys.stderr)
        return 1

    print(
        f"OK — {len(tree)} paquets, tous autorises; aucun import reseau ni IA. "
        "Le moteur est executable hors ligne."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
