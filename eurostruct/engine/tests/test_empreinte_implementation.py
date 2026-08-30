"""L'empreinte d'implémentation doit désigner le CODE, pas une phrase.

CE QUE CE FICHIER ÉTABLIT, ET POURQUOI IL EST ÉCRIT ROUGE D'ABORD
------------------------------------------------------------------
Une confirmation normative dit trois choses : *quelle règle*, *quelle valeur*,
et *quel code l'applique*. Les deux premières sont ancrées au registre par
``_ecart_de_sujet``. La troisième ne l'est pas :

``implementation_payload`` est construit à partir d'``implementation_note``,
une chaîne de caractères que **le client fournit**. L'interface y met une
phrase générique. Deux conséquences, et les deux sont des défauts :

1. **deux descriptions humaines différentes du même paramètre produisent deux
   empreintes d'implémentation différentes.** L'empreinte ne désigne donc pas
   l'implémentation : elle désigne la façon dont quelqu'un l'a décrite. Deux
   ingénieurs qui rédigent la même chose autrement signent deux sujets ;

2. **une confirmation portant une empreinte périmée ouvre encore le strict.**
   Le code qui lit et applique le paramètre peut changer entièrement — une
   formule corrigée, un facteur déplacé — sans qu'aucune confirmation ne cesse
   d'être valable. C'est exactement ce que l'empreinte existe pour empêcher.

CE QUE LE CORRECTIF DOIT DONNER
--------------------------------
L'empreinte se dérive du **chemin de code déclaré** qui lit et applique la
règle, et de la version du moteur. Elle ne dépend d'aucun texte fourni par un
client. La passerelle la **recalcule indépendamment** au moment d'évaluer : une
confirmation dont l'empreinte ne correspond plus au code déployé reste dans
l'historique et ne débloque plus rien.

CE QUI RESTE HUMAIN, ET QUI NE BOUGE PAS
-----------------------------------------
La déclaration et les citations. Elles portent la PREUVE — ce qu'une personne
a lu, où, et ce qu'elle certifie. Elles peuvent tout changer de la preuve, et
rien de la spécification ni de l'empreinte d'implémentation.
"""

from __future__ import annotations

import pytest

#: LE DECOR FICTIF EST PARTAGE AVEC `test_passerelle`, et il n'est pas
#: recopie: un second decor deriverait du premier, et les deux fichiers
#: eprouveraient alors deux paquets differents en croyant parler du meme.
from test_passerelle import (
    CLE,
    Fournisseur,
    confirmation,
    jeu_de,
    paquet,
    parametre,
)

from eurostruct_engine.ndp.confirmation import ConfirmationStatus
from eurostruct_engine.ndp.passerelle import appliquer_confirmations


@pytest.fixture(autouse=True)
def _cache_propre():
    """Le cache de l'empreinte est vidé AVANT et APRÈS chaque cas.

    ``empreinte_implementation`` est mémorisée: en production la source ne
    bouge pas pendant la vie du processus, et la recalculer à chaque paramètre
    de chaque requête coûterait trois lectures de fichier pour rien.

    Ici, un cas déplace délibérément la source. Sans ce nettoyage EN SORTIE, le
    cache garderait l'empreinte du code modifié une fois le monkeypatch défait,
    et **tous les cas suivants du processus** verraient une empreinte fausse —
    mesuré: huit cas de ``test_passerelle`` tombaient, et aucun seul.
    """
    from eurostruct_engine.ndp.implementation import empreinte_implementation

    empreinte_implementation.cache_clear()
    yield
    empreinte_implementation.cache_clear()


# ===========================================================================
# 1. L'EMPREINTE NE DOIT PAS DEPENDRE DE LA PROSE
# ===========================================================================
def test_deux_descriptions_du_meme_parametre_donnent_la_meme_empreinte() -> None:
    """MÊME règle, MÊME code, deux rédactions : une seule empreinte.

    ROUGE AUJOURD'HUI. ``composer_dossier`` hache ``implementation_note``, si
    bien que « lecture scalaire de X » et « on lit X dans le registre »
    produisent deux empreintes — donc deux sujets, pour un seul code.
    """
    from eurostruct_engine.ndp.implementation import empreinte_implementation

    a = empreinte_implementation(CLE)
    b = empreinte_implementation(CLE)
    assert a.digest == b.digest, (
        "l'empreinte d'implementation n'est pas deterministe pour une meme "
        "regle et un meme code."
    )

    # ET ELLE NE PREND AUCUN TEXTE. La signature de la fonction est le
    # contrôle: si elle acceptait une note, la prose pourrait encore la
    # déplacer.
    import inspect

    parametres = inspect.signature(empreinte_implementation).parameters
    assert list(parametres) == ["rule_id"], (
        f"empreinte_implementation prend {list(parametres)}: tout parametre "
        "supplementaire est une porte par laquelle un texte peut redefinir "
        "l'empreinte."
    )


def test_l_empreinte_nomme_le_chemin_de_code_et_la_version_du_moteur() -> None:
    """Elle doit être LISIBLE : on doit pouvoir dire ce qu'elle résume."""
    import json

    from eurostruct_engine.ndp.implementation import empreinte_implementation
    from eurostruct_engine.version import ENGINE_VERSION

    charge = json.loads(empreinte_implementation(CLE).canonical_payload)
    assert charge["kind"] == "implementation"
    assert charge["rule_id"] == CLE
    assert charge["engine_version"] == ENGINE_VERSION
    chemin = charge["code_path"]
    assert chemin, "aucun symbole declare: l'empreinte ne resume rien."
    for entree in chemin:
        assert entree["symbol"]
        assert len(entree["source_sha256"]) == 64


def test_une_regle_sans_chemin_de_code_declare_est_refusee() -> None:
    """Fail-closed. Pas de chemin déclaré, pas d'empreinte, pas de confirmation."""
    from eurostruct_engine.ndp.confirmation import ConfirmationDomainError
    from eurostruct_engine.ndp.implementation import empreinte_implementation

    with pytest.raises(ConfirmationDomainError):
        empreinte_implementation("EN 1992-1-1:parametre_sans_implementation")


# ===========================================================================
# 2. UNE EMPREINTE PERIMEE NE DOIT PLUS RIEN OUVRIR
# ===========================================================================
def test_une_confirmation_dont_l_empreinte_est_perimee_ne_debloque_plus(
        monkeypatch) -> None:
    """LE CAS DÉCISIF.

    Deux regards signent un dossier exact ; le paramètre devient utilisable.
    Puis **le code change**. La confirmation reste dans l'historique — elle est
    authentique et elle a eu lieu — mais elle ne doit plus ouvrir le strict :
    elle atteste d'un code qui n'est plus celui qui tourne.

    ROUGE AUJOURD'HUI. ``_ecart_de_sujet`` ne recalcule rien : l'empreinte
    d'implémentation du dossier n'est confrontée à aucune référence, et le
    paramètre reste utilisable après n'importe quel changement de code.
    """
    from eurostruct_engine.ndp import implementation as mod_impl
    from eurostruct_engine.ndp.implementation import empreinte_implementation

    p = parametre()
    jeu = jeu_de(p)
    signe = paquet(impl=empreinte_implementation(CLE))
    fournisseur = Fournisseur(
        (confirmation(signe, "alice"), confirmation(signe, "bob")))

    # --- avant : le chemin normal ouvre ------------------------------------
    _, rapports = appliquer_confirmations(jeu, {CLE: signe},
                                          provider=fournisseur)
    assert rapports[0].status is ConfirmationStatus.CONFIRMED
    assert rapports[0].usable

    # --- LE CODE CHANGE ----------------------------------------------------
    # On ne réécrit pas le moteur pour un test: on déplace la SOURCE que
    # l'empreinte résume, ce qui est exactement l'effet observable d'un
    # correctif dans la fonction qui applique le paramètre.
    vraie_source = mod_impl._source_du_symbole

    def source_modifiee(symbole: str) -> str:
        return vraie_source(symbole) + "\n# FICTIF — le code a change.\n"

    monkeypatch.setattr(mod_impl, "_source_du_symbole", source_modifiee)
    empreinte_implementation.cache_clear()

    _, apres = appliquer_confirmations(jeu, {CLE: signe}, provider=fournisseur)
    assert apres[0].status is not ConfirmationStatus.CONFIRMED, (
        "une confirmation attestant d'un code REVOLU ouvre encore le mode "
        "strict: l'empreinte d'implementation n'est confrontee a rien."
    )
    assert not apres[0].usable
    assert "implementation" in apres[0].reason.lower()

    # La confirmation n'a pas disparu: elle est toujours rendue par le
    # provider. Elle n'ouvre simplement plus rien.
    assert len(fournisseur.confirmations_for(CLE)) == 2


def test_la_declaration_humaine_ne_deplace_pas_l_empreinte() -> None:
    """Ce qui reste humain doit rester sans effet sur la spécification.

    La déclaration et les citations portent la preuve. Deux dossiers qui ne
    diffèrent que par elles doivent porter la MÊME empreinte
    d'implémentation et la MÊME spécification.
    """
    from eurostruct_engine.ndp.dossier import CitationDeRevue, composer_dossier

    p = parametre()
    commun = {
        "citations": (CitationDeRevue(p.source_doc_id,
                                      "FICTIF — citation relevee.", 22),),
    }
    un = composer_dossier(p, statement="FICTIF — releve par A.", **commun)
    deux = composer_dossier(p, statement="FICTIF — controle par B, "
                                         "autre redaction.", **commun)

    assert un.implementation.digest == deux.implementation.digest
    assert un.normative_spec.digest == deux.normative_spec.digest
    # La preuve, elle, DOIT bouger: c'est ce qu'elle atteste.
    assert un.statement != deux.statement
