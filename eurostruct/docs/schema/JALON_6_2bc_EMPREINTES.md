# Jalon 6.2b / 6.2c — Correctif des empreintes

**Statut : 6.2b contrôlé, réserve bloquante levée par 6.2c.** Ne remet pas en
cause l'architecture des trois empreintes ; ferme six angles morts (6.2b) puis
la pureté de la canonicalisation (6.2c, §9).

Le fil conducteur de ce correctif : **chaque durcissement demandé a fait
apparaître un défaut réel du code de 6.2**, la plupart silencieux. C'est la
raison pour laquelle ils sont listés ici séparément — un correctif qui n'aurait
rien trouvé aurait surtout prouvé que le durcissement était trop faible.

---

## 0. Ce que 6.2 laissait passer

| # | Défaut | Nature | Découvert par |
|---|---|---|---|
| 1 | `alpha_cw` n'a **aucun code propre** : son empreinte était insensible au sélecteur de branche, au contrôle des bornes, aux conversions d'unités | **faille** | exigence 1 |
| 2 | la sonde d'identité du décorateur **polluait `_IMPLEMENTATIONS`** : tous les appels après le premier levaient, et le payload portait `identity_verified: false` pour **toutes les règles sauf une** | **bug silencieux** | exigence 2 |
| 3 | `_free_names` ne liait pas les **définitions imbriquées** ni les paramètres profonds : un paramètre nommé `min` aurait été résolu en `builtins.min` et inscrit comme une dépendance jamais lue | **faille de correction** | exigence 2 |
| 4 | un **appel indirect** (`f = math.floor` puis `f(x)`) n'inscrivait aucun symbole externe et ne passait par **aucun contrôle de liste blanche** | **faille silencieuse** | exigence 6 |
| 5 | les **clés de mapping** étaient triées sur leur forme brute puis normalisées : deux écritures Unicode d'une même clé s'écrasaient l'une l'autre dans la compréhension, sans un mot | **perte de donnée silencieuse** | exigence 4 |
| 6 | les appels par attribut (`math.sqrt`) étaient **vérifiés mais pas inscrits** : le payload nommait le module, jamais le symbole | défaut de traçabilité | exigence 3 |
| 7 | la liste blanche était une **valeur par défaut d'argument**, liée à l'import : ce qui était *annoncé* et ce qui était *appliqué* pouvaient diverger | **faille** | exigence 3 |
| 8 | `builtins.getattr` figurait dans la liste du noyau, alors que `_free_names` **refuse de toute façon** tout appel à `getattr` | entrée morte | exigence 3 |
| 9 | source Python indisponible → `OSError` remontait comme une panne technique au lieu d'un refus explicite | échec non fermé | exigence 6 |

Le n° 2 est le plus grave : le champ censé attester que le décorateur rend bien
la fonction reçue disait `false` presque partout, et **personne ne le lisait**.
C'est exactement la panne qu'une exigence de vérification est censée empêcher —
elle avait été implémentée, et elle ne fonctionnait pas.

---

## 1. Noyau générique d'évaluation

### 1.1 Le problème

`alpha_cw` possède **zéro fragment d'implémentation propre**. Tout ce qu'elle
« fait » — choisir une branche, appliquer les inclusivités, vérifier le
domaine, résoudre une règle interne, convertir les unités — vit dans le moteur
générique. Tant que l'empreinte ne couvrait que le code propre, modifier le
sélecteur de branche changeait son résultat **sans changer son empreinte** :
une règle devenue fausse serait restée confirmée.

### 1.2 Composition exacte, par type de règle

`evaluation_kernel_digest(rule_type)` calcule la fermeture transitive du chemin
générique. Voici la liste **exacte** des fonctions couvertes, dans l'ordre où
elles entrent au payload. Elle est vérifiée par un test qui compare à une
constante écrite en clair, pour qu'un ajout ou un retrait soit une modification
visible du test et jamais un effet de bord.

| | `ScalarRule` | `FormulaRule` | `ConditionalRule` | `NormativeFunction` |
|---|:---:|:---:|:---:|:---:|
| `NormativeRule._validate_inputs` | ● | ● | ● | ● |
| `units.require_dimension` | ● | ● | ● | ● |
| `DomainBound.check` | ● | ● | ● | ● |
| `ScalarRule.evaluate` | ● | | | |
| `FormulaRule.evaluate` | | ● | | |
| `ConditionalRule.evaluate` | | | ● | |
| `NormativeFunction.evaluate` | | | | ● |
| `_dim_of` | | ● | | ● |
| `implementation` | | ● | | ● |
| `get_rule` | | | ● | |
| `Branch.contains` | | | ● | |
| **total** | **4** | **6** | **6** | **6** |

Les fragments non fonctionnels de ces fermetures :

| type | symboles externes | registres de liaison |
|---|---|---|
| `scalar` | `builtins.dict`, `float`, `isinstance`, `set`, `sorted`, `TypeError`, `pint.Quantity` | — |
| `formula` | + `builtins.str`, `KeyError` | `_IMPLEMENTATIONS` |
| `conditional_rule` | + `builtins.KeyError` | `_RULES` |
| `function` | + `builtins.str`, `KeyError` | `_IMPLEMENTATIONS` |

**Quatre types, quatre empreintes distinctes** — un noyau commun aux quatre
aurait fait dépendre l'empreinte d'une règle scalaire du sélecteur de branches,
qu'elle n'emprunte jamais.

### 1.3 Ce que le noyau ne contient pas, et pourquoi

`ConditionalRule` ne porte ni `FormulaRule.evaluate` ni `implementation` : elle
délègue à des règles filles, dont les empreintes d'implémentation propres — déjà
présentes dans `internal_rules` — couvrent leur propre noyau. Le noyau du type
`formula` entre donc bien dans l'empreinte d'`alpha_cw`, par ses filles.

`ScalarRule` ne porte pas `implementation` : sa valeur est une donnée, elle ne
va chercher aucune mathématique.

### 1.4 Démonstration demandée

Deux tests simulent une modification du moteur et vérifient que l'empreinte
d'`alpha_cw` bouge :

- `test_modifier_le_selecteur_de_branche_change_l_empreinte_d_alpha_cw` —
  remplace `Branch.contains` par une variante sans inclusivités, exactement le
  genre de modification qui déplace la frontière entre deux branches sans
  toucher une ligne de la règle ;
- `test_modifier_le_controle_des_bornes_change_l_empreinte_d_alpha_cw` —
  désarme `DomainBound.check`.

Les deux échouent si l'on retire `evaluation_kernel` du payload (vérifié par
mutation).

---

## 2. Politique exacte des décorateurs

### 2.1 Les trois issues possibles

| cas | traitement | ce qui entre au payload |
|---|---|---|
| décorateur **déclaré à identité vérifiée** (`implementation`) **et** sonde réussie | résumé par liaison | identité qualifiée, arguments, `binding: {rule_id, function}`, `identity_verified: true` |
| décorateur **de notre paquet**, non déclaré | **fermeture transitive entièrement résolue** | identité + `closure` complète de son code |
| tout autre | **refus** (`UnresolvableDependency`) | — |

Aucun traitement superficiel n'est appliqué par défaut. Un décorateur d'identité
extérieur parfaitement inoffensif est refusé quand même : la fermeture ne le
sait pas, et « inoffensif » n'est pas une propriété que l'on suppose.

### 2.2 La sonde d'identité, et le bug qu'elle cachait

L'affirmation « un décorateur enveloppant changerait son propre AST » ne
suffisait pas : son comportement peut aussi changer par une constante globale
ou un registre. `_verifie_identite` **appelle** donc réellement le décorateur
sur une fonction sonde et vérifie que l'objet ressorti est le même.

Or cet appel a un **effet de bord** : `implementation` inscrit ce qu'on lui
donne dans `_IMPLEMENTATIONS`. Sans restauration, le premier appel polluait le
registre et tous les suivants levaient « deux implémentations enregistrées »,
que le `except` transformait en `identity_verified: false`. Le champ censé
attester l'identité disait donc `false` pour toutes les règles sauf une.

Deux corrections :

1. les registres de liaison sont **remis dans leur état exact** après la sonde,
   quoi qu'ait fait le décorateur — vérifié par
   `test_la_sonde_d_identite_ne_laisse_aucune_trace`, qui sonde trois fois ;
2. une sonde négative sur un décorateur *déclaré* est désormais un **refus**,
   non un champ `false` que personne ne relit : si l'identité ne tient pas, ce
   qui s'exécute n'est pas ce dont on calcule l'empreinte.

### 2.3 Les deux moitiés de la liaison

Une liaison n'est vérifiable que si ses deux moitiés sont sous empreinte :

- celle qui **inscrit** — `implementation`, ajoutée au noyau des types
  `formula` et `function` ;
- celle qui **résout** — `FormulaRule.evaluate` / `NormativeFunction.evaluate`
  lisant `_IMPLEMENTATIONS`, dont le registre figure au payload comme
  `binding_registry`.

Le registre entre par son **identité et son rôle**, jamais par son contenu
vivant : y mettre les clés ferait dépendre l'empreinte de chaque règle de toutes
les autres règles enregistrées.

---

## 3. Liste blanche, symbole par symbole

### 3.1 Les listes

Deux listes **indépendantes**, et non l'une sur-ensemble de l'autre. Les
chaîner faisait entrer `math.sqrt` dans le noyau, qui ne calcule aucune racine,
et `sorted` dans le domaine d'une règle, qui ne trie rien.

**`ALLOWED_EXTERNAL_SYMBOLS`** — ce qu'une règle normative a le droit d'appeler :

| symbole | usage réel |
|---|---|
| `math.sqrt` | 9.5N — la racine de `f_ck` |
| `math.tan` | 9.6N — `cot α = 1/tan α` |
| `builtins.float` | conversions explicites de magnitude |
| `builtins.min` | 9.8N et le plafond de `cot θ_max` |
| `pint.Quantity` | construction d'une grandeur avec son unité |

**`KERNEL_ALLOWED_SYMBOLS`** — ce que le moteur d'évaluation a le droit
d'appeler : `builtins.dict`, `builtins.float`, `builtins.isinstance`,
`builtins.set`, `builtins.sorted`, `builtins.str`, `pint.Quantity`.

**`ALLOWED_EXCEPTIONS`** — `builtins.TypeError`, `builtins.KeyError`. Elles ne
calculent rien : elles refusent. Leur identité entre quand même au payload —
lever `ValueError` là où l'on levait `TypeError` change le comportement
observable de l'appelant.

### 3.2 Minimalité imposée dans les deux sens

- `_autoriser` garantit **utilisé ⊆ déclaré**, à l'exécution ;
- `test_aucun_symbole_declare_n_est_inutilise` garantit **déclaré ⊆ utilisé**.

Ensemble : égalité. Une entrée morte est un élargissement latent, et c'est ainsi
que `builtins.getattr` avait fini dans la liste du noyau — alors que
`_free_names` refuse de toute façon tout appel à `getattr`. `ValueError`,
`OSError` et `Exception` ont été retirés pour la même raison.

Le prix à payer est assumé : si une règle future cesse d'utiliser `math.tan`, le
test échoue jusqu'à ce que la liste soit réduite. C'est le comportement
recherché — la liste dit ce qui est réellement appelé, pas ce qui serait toléré.

### 3.3 Annoncé = appliqué

La liste était une **valeur par défaut d'argument**, liée à l'import : la
redéfinir changeait ce que le payload *déclare* sans changer ce qui est
*refusé*. Une liste blanche dont l'annonce et l'application peuvent diverger ne
garantit rien. Elle est désormais résolue à l'appel, et
`test_la_liste_appliquee_est_celle_qui_est_declaree` verrouille les deux sens.

### 3.4 Les quatre verrous demandés

| verrou | test |
|---|---|
| un symbole autorisé passe | `test_un_symbole_autorise_passe` (`min`) |
| un builtin non autorisé est refusé | `test_un_builtin_non_autorise_est_refuse` (`len`) |
| une fonction externe non autorisée est refusée | `test_une_fonction_externe_non_autorisee_est_refusee` (`math.floor` — `math` est une racine versionnée, `math.floor` ne l'est pas) |
| modifier la liste change les empreintes | `test_modifier_la_liste_d_autorisation_change_les_empreintes` |

Élargir ce qu'une règle a le droit d'appeler est un **changement normatif de la
méthode**, pas un réglage interne : la liste entre au payload, donc une
confirmation signée sous l'ancienne liste ne vaut plus sous la nouvelle.

---

## 4. Garanties de représentation canonique

Les neuf garanties demandées, chacune testée :

| garantie | comportement | test |
|---|---|---|
| normalisation NFC | deux écritures Unicode → même empreinte | `test_les_chaines_sont_normalisees_en_NFC` |
| encodage UTF-8 | UTF-8 réel, pas d'échappement ASCII ; digest sur les octets UTF-8 | `test_le_payload_est_de_l_UTF_8_reel_sans_echappement_ascii` |
| `NaN`, `±Inf` | **refusés**, valeurs nues et grandeurs Pint | `test_NaN_et_les_infinis_sont_refuses` |
| `-0.0` | ramené à `0.0` — même empreinte | `test_moins_zero_et_zero_donnent_la_meme_empreinte` |
| `True` / `1` / `1.0` | **trois formes distinctes** : `true`, `1`, `{"__float__":"1.0"}` | `test_True_1_et_1_0_restent_distincts` |
| ordre des mappings | clés triées ; l'ordre d'écriture est sans effet | `test_l_ordre_d_ecriture_d_un_mapping_est_sans_effet` |
| tri des ensembles | sur la **forme canonique sérialisée**, jamais sur un ordre Python | `test_les_ensembles_sont_tries_sur_leur_forme_canonique` |
| stabilité `PYTHONHASHSEED` | quatre **vrais sous-processus**, seeds 0/1/42/12345 | `test_l_empreinte_est_stable_sous_plusieurs_PYTHONHASHSEED` |
| cycles | objets **et** dépendances | `test_un_cycle_dans_une_valeur_est_refuse`, `test_un_cycle_de_dependances_ne_boucle_pas` |

`repr(float)` est conservé pour `esc-canon/1` : ces cas sont désormais
explicitement définis et testés.

### 4.1 Le défaut trouvé ici

Les clés de mapping étaient triées **sur leur forme brute** puis normalisées.
Conséquence : l'ordre était défini sur une forme absente du payload, et surtout
deux clés distinctes en Python (« é » précomposé et « e » + accent combinant) se
seraient **écrasées l'une l'autre** dans la compréhension de dictionnaire, sans
un mot. Le mapping canonique aurait porté une clé de moins que l'original.

Correction : normaliser d'abord, trier ensuite, et **refuser explicitement** une
collision. Idem côté ensembles.

Note de méthode : la première rédaction de ces tests écrivait les deux formes
Unicode **en clair**. Elles sont indiscernables dans le source, l'éditeur les a
uniformisées, et les trois tests passaient en ne vérifiant plus rien. Ils
construisent désormais les chaînes par échappements (`"é"` contre
`"é"`) et **vérifient d'abord que les deux formes diffèrent** avant de
tester quoi que ce soit d'autre.

---

## 5. `evidence_digest` — statut

**`evidence_digest` est implémenté, pas seulement préparé.** Le tableau des six
règles de 6.2 n'affichait que `normative_spec_digest` et `implementation_digest`
pour une raison de modèle, qu'il faut énoncer clairement :

> **Une règle ne porte pas de preuve.** La preuve est attachée à une
> **confirmation** — l'acte par lequel un vérificateur humain atteste avoir lu
> telle page de tel document. Cet objet n'existe pas encore : c'est l'objet du
> **jalon 6.3**.

Il n'y a donc aucune ligne « evidence » à afficher en face d'une règle, et il
n'y en aura pas : ce sera une colonne des confirmations. `EvidenceItem` et
`evidence_digest` sont en place et testés pour que 6.3 s'y branche sans
redéfinir la forme canonique.

Les six démonstrations demandées :

| demandé | résultat | test |
|---|---|---|
| modifier la citation change **uniquement** `evidence_digest` | oui, **par construction** : aucune empreinte de règle ne contient `quote`, `page_printed` ni `evidence` — vérifié sur toutes les règles du registre | `test_la_preuve_et_la_specification_sont_deux_axes_independants`, `test_retoucher_une_citation_apres_signature_est_detectable` |
| modifier `page_printed` change l'empreinte | oui | `test_changer_le_folio_change_la_preuve` |
| modifier le digest **ou le rôle** du document change l'empreinte | oui, les deux | `test_changer_de_document_change_la_preuve`, `test_changer_le_role_d_un_document_change_la_preuve` |
| modifier `page_pdf` ne change **pas** l'empreinte | oui — aide de navigation, sans autorité normative ; deux exemplaires du même document la portent différente, c'est arrivé dans ce dépôt (folio = pdf − 2 pour l'ANB, pas pour la base) | `test_la_page_pdf_ne_change_pas_la_preuve` |
| mêmes preuves dans un autre ordre → le résultat **défini par le modèle** | le modèle définit la preuve comme une **suite ordonnée** : permuter change l'empreinte | `test_l_ordre_des_preuves_compte` |
| l'ordre d'une pile normative ordonnée reste significatif | oui, sur l'axe **spécification** : permuter deux couches d'`expression_sources` change `normative_spec_digest` | `test_l_ordre_de_la_pile_normative_est_significatif` |

La citation est en outre scellée par son propre `quote_digest`, si bien que
retoucher le texte sans recalculer l'empreinte est détectable
(`test_la_citation_est_scellee_par_son_propre_digest`).

---

## 6. Échec fermé

Les six situations demandées produisent un **refus explicite**, jamais une
empreinte présentée comme complète :

| situation | test | message |
|---|---|---|
| source Python indisponible | `test_une_source_python_indisponible_est_refusee` | « source Python indisponible … aucune empreinte ne peut couvrir un code qu'on ne peut pas lire » |
| cycle de dépendances | `test_un_cycle_de_dependances_ne_boucle_pas` | fermeture **finie**, chaque fonction une seule fois |
| cycle dans une valeur | `test_un_cycle_dans_une_valeur_est_refuse` | « cycle dans la valeur à canonicaliser » |
| appel indirect | `test_appeler_un_parametre_est_refuse`, `test_appeler_un_alias_local_est_refuse` | « appel indirect … la fermeture ne peut pas dire quel code s'exécutera » |
| attribut dynamique | `test_un_attribut_dynamique_est_refuse`, `test_un_appel_dynamique_est_refuse` | « appel à 'getattr', dont la cible n'est pas déterminable » |
| décorateur inconnu | `test_un_decorateur_inconnu_est_refuse` | « décorateur '…' inconnu … aucun traitement superficiel par défaut » |
| valeur globale mutable | `test_un_etat_mutable_global_est_refuse` | « dépendance de type dict, que la fermeture ne sait pas décrire » |

### 6.1 L'appel indirect : un trou silencieux

`math.sqrt(x)` écrit directement passe par le contrôle de liste blanche. Le
**même appel** via `f = math.floor` puis `f(x)` n'inscrivait aucun symbole
externe et ne passait par aucun contrôle. Un refus manquant est mauvais ; un
contournement silencieux d'un contrôle existant est pire.

La distinction posée : un nom lié par une **définition imbriquée** est sous
empreinte (son code est dans l'AST), l'appeler est sans danger. Un nom lié par
une **valeur** — paramètre, affectation, `except … as` — ne l'est pas.

**Une seule exemption**, reconnue sur la forme exacte de l'affectation :
`fn = _IMPLEMENTATIONS[rule_id]` puis `fn(...)`. C'est le dispatch du moteur, et
il est couvert par ailleurs — le registre figure au payload, la liaison
`rule_id → fonction` est inscrite par le décorateur, et la fonction visée a sa
propre empreinte. Interdire tout appel indirect aurait rendu le noyau lui-même
incalculable ; l'autoriser largement aurait rouvert le trou.

### 6.2 Portée du contrôle des définitions imbriquées

`_free_names` ne liait ni les définitions imbriquées ni les paramètres profonds.
Au-delà du refus de trop (`implementation` retourne son `decorate` imbriqué),
c'était une faille de correction : un paramètre nommé `min` aurait été résolu
depuis les globales en `builtins.min` et **inscrit au payload comme une
dépendance que le code n'a jamais lue**. Les annotations, elles, sont
désormais exclues de la résolution — `-> bool` n'est pas un appel à `bool()`, et
les confondre aurait obligé à inscrire `builtins.bool` parmi les symboles qu'une
règle a le droit d'appeler. Elles restent capturées mot pour mot dans le dump
AST, donc les changer change bien l'empreinte.

---

## 7. Vérification

### 7.1 Commande canonique

```
$ ./run_tests.sh --require-db
 SURFACE          ETAT           DETAIL
 moteur           VERT           collectes 816 | executes 816 | reussis 816 | ignores 0 | echoues 0
 importeur        VERT           collectes 88  | executes 88  | reussis 88  | ignores 0 | echoues 0
 garanties SQL    VERT           4 groupe(s) de garanties verifie(s)
 VERDICT: COMPLET — les trois surfaces ont tourne, toutes vertes.
 code de sortie: 0
```

Base PostgreSQL 16 vierge, les neuf migrations appliquées depuis une base vide.

`test_canonical_digests.py` : **46 → 89 tests**. Moteur : **773 → 816**.

### 7.2 Les tests sont porteurs, vérifié par mutation

Un test qui passe pour une mauvaise raison est pire que pas de test. Cinq
mutations ont été injectées et **toutes ont été rattrapées** :

| mutation | tests qui tombent |
|---|---|
| `evaluation_kernel` retiré du payload | 3 |
| refus d'appel indirect désarmé | 2 |
| sonde d'identité sans restauration des registres | 2 |
| `builtins.getattr` remis comme entrée morte | 1 |
| collision de clés normalisées redevenue silencieuse | 1 |

---

## 8. Limites restantes

1. **Aucune confirmation n'existe encore.** Calculer une empreinte ne valide
   rien : la validation normative humaine reste entièrement due. C'est le jalon
   6.3, et `test_calculer_une_empreinte_ne_confirme_rien` le rappelle.

2. **`evidence_digest` n'est branché sur rien.** Il est implémenté et testé,
   mais aucune règle ne porte de preuve — voir §5. Tant que 6.3 n'existe pas,
   aucune preuve réelle n'est scellée.

3. **La frontière externe reste une frontière.** `math`, `builtins` et `pint`
   entrent par leur numéro de version, pas par leur contenu : une régression
   interne à Pint qui ne changerait pas son numéro de version ne serait pas vue.
   C'est un choix, pas un oubli — l'alternative serait d'empreindre Pint entier.

4. ~~**La sonde d'identité s'exécute au calcul de l'empreinte.**~~ **Levée par
   6.2c** — la sonde est supprimée, la preuve est statique. Voir §9.

5. **`_BINDING_REGISTRIES` et `_KNOWN_IDENTITY_DECORATORS` sont des listes
   tenues à la main.** Elles sont courtes, commentées et verrouillées par les
   tests, mais ce sont des décisions humaines, pas des propriétés déduites.

6. **L'exemption d'appel indirect est reconnue syntaxiquement.** Elle exige la
   forme `nom = REGISTRE[...]`. Une écriture équivalente mais différente
   (`nom = REGISTRE.get(...)`) serait refusée — comportement voulu, mais qui
   demandera une décision explicite si le moteur change de style.

7. **Non traité, hors périmètre 6.2b :** les quatre `open_normative_questions`,
   la confirmation visuelle de `w_max`, et la règle belge ×1,25 pour les dalles.


---

# 9. Jalon 6.2c — pureté de la canonicalisation

**Réserve bloquante levée.** Le calcul d'une empreinte n'exécute plus aucun
décorateur et ne produit plus aucun effet de bord.

## 9.1 Stratégie retenue : preuve statique conservatrice (approche 1)

`_preuve_identite_statique(deco)` établit sur le **seul AST**, sans jamais
appeler le décorateur, qu'il rend exactement la fonction reçue. Deux formes
sont reconnues :

| forme | écriture | jeton au payload |
|---|---|---|
| `direct` | `def deco(fn): …; return fn` | `esc-identity/1/direct` |
| `fabrique` | `def deco(arg): def interne(fn): …; return fn; return interne` | `esc-identity/1/fabrique` |

`implementation` est une fabrique. Trois conditions, **toutes nécessaires**, sur
la fonction qui doit rendre l'identité :

1. **aucune voie de retour ne rend autre chose** — un seul `return emballage`
   ruine la propriété ;
2. **le nom n'est jamais réaffecté** — sinon `fn = enveloppe(fn)` puis
   `return fn` satisfait la condition 1 en rendant un autre objet ;
3. **toute voie de sortie termine** par ce `return` ou par un `raise` — une
   chute en fin de corps rendrait `None`.

Pour la fabrique, la condition s'applique **deux fois** : l'extérieur doit
rendre exactement sa fonction interne, et l'interne exactement son paramètre.
Le paramètre doit être unique et sans valeur par défaut : à plusieurs
paramètres, la preuve devrait déterminer lequel porte la fonction, ce qu'elle
ne sait pas faire.

**Toute autre écriture est refusée, y compris si elle serait correcte.** Une
preuve conservatrice qui refuse trop est un obstacle visible ; une preuve trop
permissive est une fausse garantie.

La preuve passe **avant** la résolution de la fermeture. Résoudre d'abord
faisait refuser un décorateur enveloppant pour son appel indirect `fn(...)` —
un refus juste, mais qui masquait la vraie raison et aurait laissé passer une
rupture d'identité sans appel indirect.

## 9.2 Suppression de la sonde exécutée

`_verifie_identite` est **supprimée du module**, pas seulement de son chemin
d'appel — un test le vérifie (`not hasattr(C, "_verifie_identite")`).

Avec elle disparaissent la restauration des registres et sa limite : un effet de
bord ailleurs que dans les registres déclarés n'aurait pas été annulé.

Le traitement des décorateurs est en outre **unifié** : tout décorateur voit
désormais sa fermeture entièrement résolue — AST et dépendances au payload —
et le décorateur déclaré à identité y ajoute seulement sa preuve, ses arguments
et sa liaison. Conséquence directe : **toute modification du décorateur change
`implementation_digest`**, y compris une modification qui respecterait le
contrat d'identité mais changerait son comportement (par exemple ne plus écrire
dans le registre).

Un **second état** a été retiré au passage : `_IN_PROGRESS`, la garde de cycle
des règles internes, était un ensemble de portée module sur lequel on faisait
`.add()` puis `.discard()` dans un `finally`. Nul en net, donc invisible à un
instantané pris avant et après — et pourtant ni pur, ni réentrant. Il est passé
en paramètre.

## 9.3 Tests de pureté ajoutés

| # | exigence | test |
|---|---|---|
| 1 | calculer les neuf empreintes ne modifie aucun registre | `test_calculer_les_empreintes_ne_modifie_aucun_registre` |
| 2 | plusieurs calculs ne modifient aucun état mutable | `test_calculer_plusieurs_fois_ne_modifie_aucun_etat_mutable` (instantané de **tout** dict/list/set de portée module de `canonical` et `rules`) |
| 2 bis | *aucune mutation, même transitoire* | `test_le_canonicaliseur_ne_mute_aucun_etat_de_portee_module` — relit le **source** du module et refuse affectation par indice, `del`, `+=` ou méthode mutante sur un conteneur de portée module |
| 3 | l'ordre de calcul ne change ni payloads ni digests | `test_l_ordre_de_calcul_ne_change_ni_les_payloads_ni_les_digests` |
| 4 | une sentinelle modifiée par un décorateur de test reste inchangée | `test_un_decorateur_a_effet_de_bord_est_refuse_sans_etre_execute` |
| 4 bis | le décorateur **connu** n'est pas exécuté non plus | `test_aucun_decorateur_n_est_execute_pendant_le_calcul_des_empreintes` — variante qui **lève** si on l'appelle |
| 5 | un décorateur connu hors contrat est refusé | `test_un_decorateur_connu_hors_contrat_est_refuse`, plus cinq variantes paramétrées (`enveloppe`, `reaffectation`, `chute`, `fabrique_infidele`, `deux_params`) |
| 6 | digests identiques dans un processus neuf | `test_les_empreintes_sont_identiques_dans_un_processus_neuf` — compare le processus courant, qui a déjà calculé des centaines d'empreintes et monkeypatché des modules, à un processus vierge |
| 7 | `_BINDING_REGISTRIES` et `_KNOWN_IDENTITY_DECORATORS` contrôlées | `test_les_listes_tenues_a_la_main_sont_controlees` — ni entrée morte, ni usage réel non déclaré, dans les deux sens |

Le test 2 bis mérite d'être signalé : c'est celui qui aurait attrapé
`_IN_PROGRESS`. Un test d'observation avant/après ne le pouvait pas.

## 9.4 Vérification

```
$ ./run_tests.sh --require-db
 moteur           VERT   collectes 830 | executes 830 | reussis 830 | ignores 0 | echoues 0
 importeur        VERT   collectes  88 | executes  88 | reussis  88 | ignores 0 | echoues 0
 garanties SQL    VERT   4 groupe(s) de garanties verifie(s)
 VERDICT: COMPLET — les trois surfaces ont tourne, toutes vertes.
```

`test_canonical_digests.py` : 89 → **103 tests**.

Trois mutations injectées, **toutes rattrapées** :

| mutation | tests qui tombent |
|---|---|
| le canonicaliseur rappelle le décorateur | 1 |
| `_IN_PROGRESS` redevient un état de module muté puis restauré | 1 (le test structurel — l'observationnel ne le voit pas) |
| la preuve d'identité accepte tout | 9 |

## 9.5 Limites restantes après 6.2c

1. **Aucune confirmation n'existe encore** — jalon 6.3. Calculer une empreinte
   ne valide rien.

2. **`evidence_digest` n'est branché sur rien** : implémenté et testé, mais
   aucune règle ne porte de preuve (§5).

3. **La preuve d'identité est conservatrice.** Écrire `implementation`
   autrement — avec un `try/finally`, un `match`, ou deux décorateurs internes —
   serait refusé même si correct. C'est le compromis assumé : le refus est
   visible et se corrige, une preuve permissive ne se voit pas.

4. **La frontière externe reste une frontière.** `math`, `builtins` et `pint`
   entrent par leur numéro de version, pas par leur contenu.

5. **`_BINDING_REGISTRIES` et `_KNOWN_IDENTITY_DECORATORS` restent des listes
   tenues à la main**, désormais verrouillées dans les deux sens (§9.3, test 7),
   mais ce sont toujours des décisions humaines.

6. **L'exemption d'appel indirect est reconnue syntaxiquement** :
   `nom = REGISTRE[...]`. `REGISTRE.get(...)` serait refusé.

7. **La pureté est prouvée sur `canonical.py` seul.** Le test structurel lit ce
   module ; il ne parcourt pas `rules.py`. C'est cohérent — seul le
   canonicaliseur est tenu d'être pur — mais cela reste une portée à connaître.
