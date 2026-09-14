"""L'empreinte doit couvrir la SÉMANTIQUE EXÉCUTABLE, pas trois en-têtes.

CE QUI NE VA PAS AUJOURD'HUI
-----------------------------
``empreinte_implementation`` hache le texte source de **trois symboles
racines** : ``ParameterSet.get``, ``NationalParameter.usable_in_strict_mode``
et ``design_flexure``. Elle ne suit aucune des fonctions qu'ils appellent.

``design_flexure`` est un orchestrateur : il lit ``ParameterSet.find``, calcule
``Concrete.fcd``, ``Reinforcement.fyd``, et conclut par ``moment_resistance``.
**C'est là que vivent les nombres.** Corriger ``fcd`` — un facteur déplacé, un
coefficient partiel appliqué au mauvais endroit — change tous les résultats du
pays, et l'empreinte ne bouge pas. Une confirmation signée pour l'ancien code
continue d'ouvrir le mode strict.

Le test existant déplace artificiellement le texte d'un symbole **déjà haché**.
Il prouve que hacher du texte détecte un changement de ce texte. Il ne prouve
rien sur la couverture — et c'est la couverture qui est en cause.

LES QUATRE FAITS ÉTABLIS ICI
-----------------------------
1. modifier la **logique d'une dépendance appelée** change l'empreinte ;
2. modifier la **logique de la racine** change l'empreinte ;
3. ajouter un **commentaire** ou changer le **formatage** ne la change pas ;
4. modifier une fonction **sans rapport** avec la règle ne la change pas.

Les faits 3 et 4 sont ceux qui rendent l'empreinte utilisable. Une empreinte
qui bouge à chaque reformatage invaliderait toutes les confirmations à chaque
passage d'un formateur, et l'équipe finirait par la contourner.

COMMENT ON MODIFIE LE CODE SANS L'ÉCRIRE
------------------------------------------
On ne réécrit pas le moteur pour un test. On remplace la **source lue** par la
fermeture transitive, ce qui est exactement l'effet observable d'un correctif :
``_source_du_symbole`` est le point unique par lequel toute source passe.
"""
from __future__ import annotations

import pytest

#: LES SYMBOLES DE LA CHAINE EC2 EN FLEXION, tels que le moteur les nomme.
#: Aucun n'est une racine declaree: tous doivent etre atteints par fermeture.
DEPENDANCES = [
    "eurostruct_engine.ndp.registry:ParameterSet.find",
    "eurostruct_engine.materials.concrete:Concrete.fcd",
    "eurostruct_engine.materials.reinforcement:Reinforcement.fyd",
    "eurostruct_engine.ec2.beam_flexure:moment_resistance",
]

#: LA REGLE ECLAIREE PAR CES PREUVES. Belge, en flexion: c'est celle dont le
#: chemin de code est declare depuis le lot precedent.
REGLE = "EN 1992-1-1:alpha_cc"

#: UNE FONCTION SANS AUCUN RAPPORT AVEC LE CALCUL EN FLEXION. Elle sert au
#: quatrieme fait: l'empreinte ne doit pas bouger quand elle bouge.
ETRANGERE = "eurostruct_engine.legal:notice"


@pytest.fixture(autouse=True)
def _cache_propre():
    """Le cache est vidé AVANT et APRÈS chaque cas.

    ``empreinte_implementation`` est mémorisée: en production la source ne
    bouge pas pendant la vie du processus. Ici chaque cas la déplace, et sans
    nettoyage EN SORTIE le cache garderait l'empreinte du code modifié une
    fois le monkeypatch défait — tous les cas suivants du processus verraient
    alors une empreinte fausse.
    """
    from eurostruct_engine.ndp.implementation import empreinte_implementation

    empreinte_implementation.cache_clear()
    yield
    empreinte_implementation.cache_clear()


def _empreinte() -> str:
    from eurostruct_engine.ndp.implementation import empreinte_implementation

    return empreinte_implementation(REGLE).digest


def _remplacer_source(monkeypatch, cible: str, transformation) -> None:
    """Déplace la source LUE d'un symbole, et d'un seul.

    C'est le point unique par lequel toute source passe: patcher ici est
    l'équivalent observable d'un correctif appliqué à ce symbole-là.
    """
    from eurostruct_engine.ndp import implementation as mod
    from eurostruct_engine.ndp.implementation import empreinte_implementation

    vraie = mod._source_du_symbole

    def _lue(symbole: str) -> str:
        source = vraie(symbole)
        return transformation(source) if symbole == cible else source

    monkeypatch.setattr(mod, "_source_du_symbole", _lue)
    empreinte_implementation.cache_clear()


# ===========================================================================
# 1. UNE DEPENDANCE APPELEE EST COUVERTE
# ===========================================================================
@pytest.mark.parametrize("dependance", DEPENDANCES)
def test_modifier_la_logique_d_une_dependance_change_l_empreinte(
        monkeypatch, dependance) -> None:
    """LE CAS DÉCISIF, ET IL EST ROUGE.

    ``Concrete.fcd`` produit la résistance de calcul du béton : elle entre
    dans chaque nombre du résultat. Une correction de sa logique doit
    invalider les confirmations signées pour l'ancien code — c'est
    exactement ce que l'empreinte existe pour garantir.

    Aujourd'hui l'empreinte ne couvre que trois racines et ne bouge pas.
    """
    avant = _empreinte()
    _remplacer_source(monkeypatch, dependance,
                      lambda s: s + "\n    _fictif = 1 / 3  # logique modifiee\n")
    apres = _empreinte()
    assert apres != avant, (
        f"modifier la LOGIQUE de {dependance} ne change pas l'empreinte: "
        "elle ne couvre pas cette dependance, et une confirmation signee "
        "pour l'ancien code continue d'ouvrir le mode strict.")


def test_les_dependances_sont_nommees_dans_l_empreinte(monkeypatch) -> None:
    """Elle doit être LISIBLE: on doit pouvoir dire ce qu'elle résume.

    Une empreinte qui bouge sans qu'on puisse énumérer ce qu'elle couvre se
    lit comme un oracle. Le payload canonique nomme chaque symbole atteint.
    """
    import json

    from eurostruct_engine.ndp.implementation import empreinte_implementation

    charge = json.loads(empreinte_implementation(REGLE).canonical_payload)
    atteints = {e["symbol"] for e in charge["code_path"]}
    manquants = [d for d in DEPENDANCES if d not in atteints]
    assert not manquants, (
        f"l'empreinte ne nomme pas {manquants}: elle ne couvre que "
        f"{sorted(atteints)}.")


# ===========================================================================
# 2. LA RACINE ELLE-MEME RESTE COUVERTE
# ===========================================================================
def test_modifier_la_logique_de_design_flexure_change_l_empreinte(
        monkeypatch) -> None:
    """La fermeture transitive ne doit pas faire perdre les racines."""
    avant = _empreinte()
    _remplacer_source(monkeypatch,
                      "eurostruct_engine.ec2.beam_flexure:design_flexure",
                      lambda s: s + "\n    _fictif = 2  # logique modifiee\n")
    assert _empreinte() != avant


# ===========================================================================
# 3. LA PROSE ET LE FORMATAGE NE COMPTENT PAS
# ===========================================================================
def test_un_commentaire_ne_change_pas_l_empreinte(monkeypatch) -> None:
    """CE QUI REND L'EMPREINTE UTILISABLE.

    Une empreinte qui bouge à chaque reformatage invaliderait toutes les
    confirmations au premier passage d'un formateur, et l'équipe finirait par
    la contourner — ce qui vaut moins qu'une empreinte absente, parce que
    celle-là inspire confiance.

    ROUGE AUJOURD'HUI: la source est hachée telle quelle, commentaires
    compris.
    """
    avant = _empreinte()
    _remplacer_source(
        monkeypatch, "eurostruct_engine.ec2.beam_flexure:design_flexure",
        lambda s: "# FICTIF — un commentaire ajoute.\n" + s
                  + "\n    # FICTIF — un autre, a la fin.\n")
    assert _empreinte() == avant, (
        "ajouter un commentaire change l'empreinte: elle hache du texte, pas "
        "de la semantique.")


def test_le_formatage_ne_change_pas_l_empreinte(monkeypatch) -> None:
    """Lignes vides, espaces en fin de ligne, indentation du bloc entier."""
    import textwrap

    avant = _empreinte()
    _remplacer_source(
        monkeypatch, "eurostruct_engine.ec2.beam_flexure:design_flexure",
        lambda s: "\n\n" + textwrap.indent(s, "    ").replace("\n", "   \n", 3)
                  + "\n\n")
    assert _empreinte() == avant, (
        "reindenter ou aerer la source change l'empreinte.")


def test_une_docstring_reecrite_ne_change_pas_l_empreinte(monkeypatch) -> None:
    """La documentation d'une fonction n'est pas son comportement.

    C'est le cas le plus frequent en pratique: on precise un `:param:`, on
    corrige une faute, et toutes les confirmations du pays tomberaient.
    """
    avant = _empreinte()
    _remplacer_source(
        monkeypatch, "eurostruct_engine.materials.concrete:Concrete.fcd",
        lambda s: s.replace('"""', '"""FICTIF — docstring reecrite. ', 1))
    assert _empreinte() == avant


# ===========================================================================
# 4. CE QUI N'A RIEN A VOIR NE COMPTE PAS
# ===========================================================================
def test_une_fonction_sans_rapport_ne_change_pas_l_empreinte(
        monkeypatch) -> None:
    """Sinon l'empreinte designerait « le depot », pas « cette regle ».

    Une empreinte qui bouge quand `legal.notice` change ne dit plus rien sur
    le code qui applique le parametre: elle mesurerait la date du dernier
    commit, ce qu'un numero de version fait deja, et plus mal.
    """
    from eurostruct_engine.ndp import implementation as mod

    avant = _empreinte()
    _remplacer_source(monkeypatch, ETRANGERE,
                      lambda s: s + "\n    _fictif = 3\n")
    assert _empreinte() == avant, (
        f"modifier {ETRANGERE} change l'empreinte de {REGLE}: la fermeture "
        "ratisse au-dela de la regle.")

    # ET ELLE N'EST PAS ATTEINTE DU TOUT. On le constate, plutot que de le
    # deduire de l'egalite ci-dessus — deux raisons differentes peuvent
    # produire la meme egalite.
    import json

    from eurostruct_engine.ndp.implementation import empreinte_implementation

    charge = json.loads(empreinte_implementation(REGLE).canonical_payload)
    assert ETRANGERE not in {e["symbol"] for e in charge["code_path"]}
    assert mod is not None


# ===========================================================================
# 5. UNE DEPENDANCE IRRESOLUBLE EST UN REFUS
# ===========================================================================
def test_une_dependance_irresoluble_est_un_refus(monkeypatch) -> None:
    """FAIL-CLOSED. On ne hache pas « ce qu'on a pu lire ».

    Une fermeture qui ignorerait en silence un symbole illisible produirait
    une empreinte qui couvre MOINS que ce qu'elle pretend couvrir, et
    personne ne le verrait. C'est le meme choix qu'a la carte declaree: ce
    qui se trompe doit se tromper bruyamment.
    """
    from eurostruct_engine.ndp import implementation as mod
    from eurostruct_engine.ndp.confirmation import ConfirmationDomainError
    from eurostruct_engine.ndp.implementation import empreinte_implementation

    #: ON CASSE `inspect.getsource`, PAS LE TRADUCTEUR. `_source_du_symbole`
    #: convertit `OSError` en refus du domaine: remplacer la fonction entiere
    #: eprouverait le monkeypatch, pas le produit.
    def _illisible(_objet):
        raise OSError("FICTIF — source indisponible")

    monkeypatch.setattr(mod.inspect, "getsource", _illisible)
    empreinte_implementation.cache_clear()
    with pytest.raises(ConfirmationDomainError):
        empreinte_implementation(REGLE)
