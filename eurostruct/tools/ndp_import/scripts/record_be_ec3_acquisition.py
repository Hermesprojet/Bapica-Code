#!/usr/bin/env python3
"""Record the acquisition and reading of NBN EN 1993-1-1 ANB (acier).

Why this stops at the catalogue
-------------------------------
The Belgian steel annex is in hand and readable (53 pages, text layer). It does
NOT, however, let us populate the parameters that matter most in a steel
calculation. For §6.1 it says:

    « 6.1(1)B Les valeurs recommandees sont normatives. »

and does not print them. gamma_M0, gamma_M1 and gamma_M2 live in the *base*
standard, NBN EN 1993-1-1:2005 §6.1, which we do not hold. Writing 1,00 / 1,00
/ 1,25 from memory would be interdiction 2: a value with no traced source.

So no EN 1993-1-1 annex is created in the engine dataset. An annex entry
carrying five secondary buckling coefficients and no partial factor would read
as "steel is covered" when it is not. The catalogue says what we have, the
constat says what it contains, and the missing document is named.

Run from tools/ndp_import/:
    python scripts/record_be_ec3_acquisition.py [--dry-run]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
CATALOGUE = HERE / "src/ndp_import/data/catalogue.json"

DOC_KEY = "BE-EN199311-NA"

#: sha256 of the deposited file. The catalogue records WHICH file was read, not
#: merely that "a" copy of the standard exists somewhere.
DOC_SHA256 = "414d8489b193742296882c8c27d815529c41a9ef9695bc7553e1ee98b0bcff8d"

#: Read on the cover page, to be DECLARED by the depositor. Never inferred.
EDITION_READ_FROM_COVER = "1e ed., decembre 2010"
PUBLICATION_AUTHORISED = "2010-05-19"
BASE_STANDARD = "NBN EN 1993-1-1, 2e ed., octobre 2005"

NOTES = (
    "ACQUIS en version texte (53 pages, 74881 caracteres), langue francaise. "
    "Metadonnees ci-dessus LUES sur la page de garde, a DECLARER par le "
    "deposant. La page de garde precise: « La norme NBN EN 1993-1-1 ne peut "
    "etre utilisee en Belgique qu'en combinaison avec son annexe nationale. » "
    "LIMITE MAJEURE: pour §6.1 l'ANB indique « Les valeurs recommandees sont "
    "normatives » SANS les imprimer. gamma_M0/M1/M2 ne peuvent donc PAS etre "
    "renseignes a partir de ce seul document: il faut la base "
    "NBN EN 1993-1-1:2005 §6.1, non detenue. Aucune annexe EN 1993-1-1 n'est "
    "creee dans le jeu de donnees du moteur tant que ce manque subsiste. "
    "Voir docs/CONSTAT_ANB_BE_EC3.md."
)

#: Values the ANB prints itself, with the page they were read on. Transcribed
#: here for the reviewer; NOT loaded into the engine (see module docstring).
READ_VALUES: dict[str, tuple[str, int, str]] = {
    "alpha_cr_min_plastique": (
        "10", 18,
        "§5.2.1(3): « Pour l'analyse plastique des structures de batiments, une "
        "valeur limite inferieure egale a 10 pour alpha_cr est normative. » "
        "L'EN recommande 15 pour l'analyse plastique: ECART A CONFIRMER contre "
        "la base, non detenue.",
    ),
    "k_imperfection_element": (
        "0,5", 18, "§5.3.4(3): « La valeur recommandee k = 0,5 est normative. »",
    ),
    "lambda_LT_0": (
        "0,2 ou 0,4", 19,
        "§6.3.2.3(1): 0,2 (avec beta = 1,0) si M_cr est determine sur la section "
        "brute; 0,4 (avec beta = 0,75) pour les poutres de batiments avec "
        "maintiens, A CONDITION que les maintiens soient totalement ignores "
        "pour la determination de M_cr. VALEUR CONDITIONNELLE: un scalaire ne "
        "peut pas la porter.",
    ),
    "beta_deversement": (
        "1,0 ou 0,75", 19,
        "§6.3.2.3(1): couple indissociable de lambda_LT_0 ci-dessus. Meme "
        "condition, meme impossibilite de la reduire a un scalaire.",
    ),
    "lambda_c_0": (
        "0,5", 20, "§6.3.2.4(1)B: « La valeur lambda_c,0 = 0,5 est normative. »",
    ),
    "k_fl": (
        "1,10", 20, "§6.3.2.4(2)B: « La valeur recommandee k_fl = 1,10 est normative. »",
    ),
    "temperature_service_min": (
        "0 degC", 17,
        "§3.2.3(1): pour les structures a l'interieur de batiments chauffes, "
        "temperature minimale de service 0 degC. Sinon, renvoi a la "
        "NBN EN 1991-1-5. Le client peut imposer d'autres valeurs.",
    ),
}

#: Scalars the ANB defers to the base standard, which we do not hold. They are
#: genuine parameters with a search pattern; only their VALUE is out of reach.
DEFERRED_TO_BASE_SCALAR: dict[str, tuple[int, str]] = {
    "gamma_M0": (19, "§6.1(1)B: « Les valeurs recommandees sont normatives. »"),
    "gamma_M1": (19, "§6.1(1)B: idem."),
    "gamma_M2": (19, "§6.1(1)B: idem."),
    "alpha_LT": (19, "§6.3.2.2(2): « Les valeurs recommandees pour alpha_LT sont normatives. »"),
}

#: Deferred too, but to whole tables or qualitative rules — not scalars.
DEFERRED_TO_BASE_NON_SCALAR: dict[str, tuple[int, str]] = {
    "table_3_2_epaisseur": (
        18, "§3.2.4(1): « La classification recommandee au tableau 3.2 est "
            "normative pour les batiments. » C'est un tableau entier.",
    ),
    "table_5_1_imperfections": (
        18, "§5.3.2(3): « Les valeurs recommandees au tableau 5.1 sont "
            "normatives. » Tableau entier, avec une reinterpretation belge des "
            "termes « analyse elastique/plastique ».",
    ),
    "ductilite": (
        17, "§3.2.2(1): « Les valeurs recommandees sont normatives. » Trois "
            "criteres de ductilite, pas un nombre.",
    ),
}

#: Choices that are not numbers at all.
METHOD_CHOICES: dict[str, tuple[int, str]] = {
    "interaction_flexion_compression": (
        20,
        "§6.3.3(5): « La methode 1 est normative. » L'annexe A de la "
        "NBN EN 1993-1-1:2005 est normative en Belgique; l'annexe B « n'est PAS "
        "d'application en Belgique » (p.21). Un moteur qui implementerait la "
        "methode 2 serait hors reglementation belge.",
    ),
    "proprietes_materiaux": (7, "§3.2.1(1): « L'option “a” est normative. »"),
    "annexes_belges_propres": (
        21,
        "Les annexes C a G ANB definissent des methodes BELGES pour M_cr, "
        "N_cr/N_cr,T/N_cr,TF, L_cr et lambda_LT. Elles n'existent pas dans l'EN: "
        "un moteur conforme en Belgique doit les implementer, pas seulement "
        "parametrer l'EN.",
    ),
}


# ---------------------------------------------------------------------------
# NBN EN 1993-1-2 ANB — acier, calcul au feu
# ---------------------------------------------------------------------------
FIRE_DOC_KEY = "BE-EN199312-NA"
FIRE_SHA256 = "25250fb818ee3bc1c81ab37d95ed286aae3d282a9757b0ea97ecf254224ea344"
FIRE_EDITION = "1e ed., decembre 2010"
FIRE_BASE = "NBN EN 1993-1-2, 2e ed., octobre 2005"

FIRE_NOTES = (
    "ACQUIS en version texte (17 pages, 18870 caracteres), langue francaise. "
    "Metadonnees LUES sur la page de garde, a DECLARER par le deposant. "
    "Page 5: « Tous les NDP sont fixes par la presente ANB » — contrairement a "
    "l'ANB 1-1, aucun choix n'est laisse au projet individuel. "
    "LIMITE MAJEURE: filigrane vertical « NATIONAL MIRROR COMMITTEE » dont les "
    "lettres s'intercalent DANS les nombres des tableaux 4.1a a 4.1e ANB et "
    "4.5 ANB (« 5E61 » pour 561, « 4M57 » pour 457, « R722 » pour 722). "
    "L'extracteur ecarte ces pages et ne propose rien depuis elles. Les "
    "temperatures critiques par elancement ne sont donc PAS transcriptibles "
    "automatiquement: relecture humaine sur le document original obligatoire. "
    "Voir docs/CONSTAT_ANB_BE_EC3.md."
)

#: Valeurs en prose, hors tableaux filigranes, avec leur page.
FIRE_READ_VALUES: dict[str, tuple[str, int, str]] = {
    "gamma_M_fi": (
        "1,0", 6,
        "§2.3(1) et §2.3(2): « La valeur gamma_M,fi = 1,0 est normative. » "
        "Enoncee deux fois, pour les deux clauses.",
    ),
    "theta_crit_classe_4": (
        "350 degC", 9,
        "§4.2.3.6(1): « La valeur theta_crit = 350 degC est normative. » "
        "Elements de section de Classe 4.",
    ),
    "theta_crit_poutre_isostatique": (
        "540 degC", 9,
        "§4.2.4(2): courbe temperature/temps normalisee, aciers S235 a S460, "
        "elements de classe 1 a 3 en batiments courants. 540 degC pour poutres "
        "isostatiques et elements tendus.",
    ),
    "theta_crit_poutre_hyperstatique": (
        "570 degC", 9, "§4.2.4(2): 570 degC pour poutres hyperstatiques.",
    ),
    "theta_crit_comprime": (
        "500 degC", 9,
        "§4.2.4(2): 500 degC pour elements comprimes et elements soumis a la "
        "flexion et a la compression axiale.",
    ),
}

#: Tables the watermark makes unreadable. Named so the gap is explicit.
FIRE_UNREADABLE: dict[str, tuple[int, str]] = {
    "k_c_facteur_correction": (
        7,
        "Tableau 4.4 ANB: k_c = 0,6+0,3psi+0,15psi^2, avec k_c <= 1 pour "
        "-1 <= psi <= 1; k_c = 1 pour d'autres diagrammes de moment. FORMULE "
        "dependant du diagramme de moment, pas un scalaire.",
    ),
    "tableau_4_1a_a_4_1e_ANB": (
        11,
        "Temperatures critiques des colonnes comprimees (S235/S275/S355/S420/"
        "S460) selon l'elancement relatif et le taux d'utilisation. Pages 11 a "
        "15, filigrane traversant les nombres.",
    ),
    "tableau_4_5_ANB_temperature": (
        16,
        "Temperature de l'acier apres 30 min d'exposition au feu normalise, "
        "selon k_sh A_m/V. Page 16, meme filigrane.",
    ),
    "tableau_4_5_ANB_deversement": (
        8,
        "Limites inferieures de lambda_LT,theta,com requerant la verification "
        "au deversement. Page 8: le tableau est une IMAGE, aucun texte "
        "extractible, filigrane en plus.",
    ),
}


def _apply(entry: dict, *, sha: str, edition: str, base: str, notes: str,
           expected: list[str], not_scalar: dict[str, str]) -> None:
    """Fill one catalogue entry.

    ``parameters_expected`` carries only names the extractor can search for —
    a test enforces that each has a pattern. Method choices and unreadable
    tables are real findings but not scalar parameters; they go in their own
    field rather than being smuggled into the parameter list.
    """
    entry["status"] = "acquired"
    entry["doc_id_sha256"] = sha
    entry["edition_read_from_cover"] = edition
    entry["publication_authorised"] = PUBLICATION_AUTHORISED
    entry["annexes_base_standard"] = base
    entry["acquisition"]["notes"] = notes
    entry["parameters_expected"] = sorted(expected)
    entry["non_scalar_findings"] = dict(sorted(not_scalar.items()))


def main(argv: list[str]) -> int:
    data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    by_key = {e["doc_key"]: e for e in data["documents"]}

    _apply(
        by_key[DOC_KEY], sha=DOC_SHA256, edition=EDITION_READ_FROM_COVER,
        base=BASE_STANDARD, notes=NOTES,
        expected=[*READ_VALUES, *DEFERRED_TO_BASE_SCALAR],
        not_scalar={
            k: f"p.{p} — {why}" for k, (p, why) in
            {**METHOD_CHOICES, **DEFERRED_TO_BASE_NON_SCALAR}.items()
        },
    )
    _apply(
        by_key[FIRE_DOC_KEY], sha=FIRE_SHA256, edition=FIRE_EDITION,
        base=FIRE_BASE, notes=FIRE_NOTES,
        expected=[*FIRE_READ_VALUES],
        not_scalar={
            k: f"p.{p} — {why}" for k, (p, why) in FIRE_UNREADABLE.items()
        },
    )

    if "--dry-run" not in argv:
        CATALOGUE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    print(f"{DOC_KEY}: acquis, sha256 {DOC_SHA256[:16]}...")
    print(f"  {len(READ_VALUES)} valeur(s) imprimees dans l'ANB et transcrites")
    print(f"  {len(DEFERRED_TO_BASE_SCALAR)} scalaire(s) renvoyes a la base "
          "EN 1993-1-1:2005, NON DETENUE")
    print(f"  {len(DEFERRED_TO_BASE_NON_SCALAR)} renvoi(s) a des tableaux entiers de la base")
    print(f"  {len(METHOD_CHOICES)} choix de methode (non numeriques)")
    print()
    print(f"{FIRE_DOC_KEY}: acquis, sha256 {FIRE_SHA256[:16]}...")
    print(f"  {len(FIRE_READ_VALUES)} valeur(s) lisibles en prose")
    print(f"  {len(FIRE_UNREADABLE)} tableau(x) ILLISIBLES (filigrane dans les chiffres)")
    print()
    print("AUCUNE annexe EN 1993 n'est creee dans le jeu de donnees du moteur.")
    print("gamma_M0/M1/M2 sont irrecuperables sans la base NBN EN 1993-1-1:2005,")
    print("qui n'a pas ete deposee. Creer l'annexe sans eux ferait croire que")
    print("l'acier est couvert.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(HERE / "src"))
    raise SystemExit(main(sys.argv))
