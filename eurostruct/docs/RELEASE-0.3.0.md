# eurostruct-engine 0.3.0 — note de release

> **Changement de valeur.** Le contrat de versionnement (`docs/VALIDATION.md`
> §3) exige qu'un résultat déjà produit ne change jamais silencieusement.
> Cette release en change plusieurs. Voici lesquels et pourquoi.

## Cause unique

Le paramètre national `EN 1992-1-1:alpha_cc` passe de **1,0 à 0,85** pour la
Belgique.

La valeur 1,0 était un **provisoire** : la recommandation de l'Eurocode,
déposée en attendant de pouvoir lire l'Annexe Nationale. La version texte de
`NBN EN 1992-1-1 ANB` (1ʳᵉ éd., août 2010) a été fournie et lue. §3.1.6 (1)P,
page 10 :

> « Pour les vérifications à l'état limite ultime (ELU) de la résistance à
> l'effort normal, la flexion simple ou composée, **la valeur de α_cc vaut
> 0,85**. Pour les autres cas, α_cc vaut 1,0. »

La Belgique s'écarte donc de la recommandation. Conserver 1,0 aurait produit
des sections sous-dimensionnées.

> ⚠️ Le paramètre reste **`pending_verification`**. Le mode strict refuse
> toujours de calculer. La valeur a été *lue* par le pipeline d'import, pas
> *confirmée* par un ingénieur habilité.

## Valeurs modifiées — cas de référence

300 × 600 mm, d = 550 mm, C30/37, B500B, M_Ed = 250 kN·m, 4 HA20 :

| Sortie | 0.2.0 (α_cc = 1,0) | 0.3.0 (α_cc = 0,85) | écart |
|---|---|---|---|
| `f_cd` | 20,0000 MPa | 17,0000 MPa | −15,00 % |
| `mu` | 0,13774105 | 0,16204829 | +17,65 % |
| `xi` | 0,18601728 | 0,22233318 | +19,52 % |
| `x_mm` | 102,30950 | 122,28325 | +19,52 % |
| `z_mm` | 509,07620 | 501,08670 | −1,57 % |
| `eps_s` | 0,01531546 | 0,01224214 | −20,07 % |
| `As_strength_mm2` | 1129,49692 | 1147,50601 | +1,59 % |
| `As_required_mm2` | 1129,49692 | 1147,50601 | +1,59 % |
| `M_Rd_kNm` | 275,62404 | 271,23413 | −1,59 % |
| `utilisation` | 0,90703265 | 0,92171291 | +1,62 % |

Inchangés : `As_min_mm2` (248,517), `As_max_mm2` (7200,0), `xi_lim` (0,448),
`As_provided_mm2` (1256,637) — aucun ne dépend de α_cc.

### Chaînes imprimées dans la note de calcul

| | 0.2.0 | 0.3.0 |
|---|---|---|
| `f_cd` | `1 · 30 MPa / 1.5` | `0.85 · 30 MPa / 1.5` |
| `mu` | `… · 1 · 20 MPa)` | `… · 1 · 17 MPa)` |

## Conséquence de dimensionnement, plus lourde que les +1,6 % d'acier

Le **moment maximal admissible avant refus** passe de **534 à 454 kN·m** sur
cette section, à −15 %. Une poutre acceptée en 0.2.0 peut être **refusée** en
0.3.0.

Un cas de la suite de propriétés l'a montré immédiatement : une section
450 × 400 mm chargée à 250 kN·m, qui passait avec α_cc = 1,0, dépasse μ_lim
avec 0,85 et déclenche `compression_reinforcement_required`. Le test a été
restreint aux hauteurs qui restent dans le domaine, ce qui est le comportement
attendu, pas un contournement.

## Cas de référence régénérés

Les cinq cas `manual_reference` de la bibliothèque ont été recalculés par
dichotomie avec α_cc = 0,85. Leur méthode reste indépendante du moteur ; seule
l'hypothèse nationale change, et elle est désormais citée dans chaque cas.

| Cas | A_s 0.2.0 | A_s 0.3.0 |
|---|---|---|
| EC2-BF-001 | 1129,497 | 1147,506 |
| EC2-BF-002 | 664,534 | 675,590 |
| EC2-BF-003 | 1989,441 | 2015,253 |
| EC2-BF-004 | 340,441 | 344,780 |
| EC2-BF-005 | 62,989 | 63,035 |

Le cas `EC2-BF-001` à M_Ed = 500 kN·m a été retiré du jeu d'équilibre
indépendant : avec α_cc = 0,85, il sort du domaine de validation.

## Un paramètre devenu inexprimable

`EN 1992-1-1:cot_theta_max` **n'a plus de valeur**. L'ANB §6.2.3 (2), page 17,
ne retient pas la borne 2,5 :

> cot θ_max = (2 + k₁·σ_cp·b_w·d·s / (A_sw·z·f_ywd)) ≤ 3, avec σ_cp ≤ 0,2·f_cd

C'est une **formule** dépendant de l'effort normal et du ferraillage. Le modèle
de paramètre ne stocke qu'un scalaire : écrire 2,5 ou 3 serait faux dans les
deux cas.

Le premier jet se contentait de l'écrire dans les `notes` en laissant 2,5 dans
`parameter_value`. C'était insuffisant : hors mode strict, `get()` rendait
toujours 2,5, c'est-à-dire exactement la valeur que l'annexe belge ne retient
pas. Une note n'empêche personne de lire un nombre.

Le statut **`not_representable`** est donc ajouté au modèle, et
`parameter_value` devient nullable :

| | `deprecated` | `not_representable` |
|---|---|---|
| ce qui est stocké | une valeur, connue fausse | rien |
| refusé en mode strict | oui | oui |
| refusé hors mode strict | oui | oui |
| débloqué par une signature d'ingénieur | non, par une nouvelle édition | **non, jamais** — il n'y a pas de scalaire à confirmer |

- `NationalParameter.__post_init__` impose l'équivalence : valeur absente
  ⟺ statut `not_representable`. Une valeur perdue pendant un import ne peut
  plus ressembler à une absence délibérée.
- Migration `0007_ndp_not_representable.sql` : valeur d'enum, colonne nullable,
  et la contrainte `value_absent_iff_not_representable` qui répète l'invariant
  côté base — la garantie doit tenir même si elle est contournée par le code.
- Nouvelle exception `UnrepresentableNationalParameter`, distincte de
  `UnverifiedNationalParameter` : le message dit qu'aucune vérification humaine
  ne débloquera le calcul, et que c'est le module qui doit être étendu.

`en_recommended` conserve 2,5 : la note de calcul doit pouvoir dire de quoi la
Belgique s'écarte.

## Un test de base de données qui avait cessé de prouver quelque chose

`db/test/02_ndp_versioning.sql` vérifiait qu'on ne peut pas écraser une valeur
nationale en place, en tentant `update … set parameter_value = 0.85`. Le
déclencheur `forbid_ndp_value_rewrite()` ne refuse que les changements *réels*
(`is distinct from`) — ce qui est correct. Mais dès que le seed belge est passé
à 0,85, cet `update` est devenu un no-op : il ne déclenchait plus rien, et le
test échouait en annonçant qu'une valeur avait pu être écrasée.

La valeur d'essai est maintenant dérivée de la valeur en base
(`current_value + 1`) au lieu d'être écrite en dur. Le test redevient
indépendant du jeu de données, dans les deux sens : il ne peut plus passer à
tort ni échouer à tort quand un paramètre bouge.

## Ce qui n'a pas changé

- Aucun paramètre n'est passé en `confirmed`.
- Le mode strict bloque toujours : 8 bloquants sur 8 requis.
- La séparation moteur / importeur, l'isolement réseau, le workflow de
  validation : intacts.
- Le contrat TypeScript reste synchronisé (`parameter_value: number | null`,
  `"not_representable"` dans l'énumération), régénéré et vérifié par la CI.

## Ce qui reste ouvert

- Les 8 paramètres bloquants attendent la décision **nominative** d'un
  ingénieur habilité. NBN édite la norme ; l'éditeur d'un document n'est pas
  celui qui engage sa responsabilité sur une étude. Il faut un nom de personne
  et une date.
- `ruff` et `mypy` sont configurés dans `engine/pyproject.toml` mais absents du
  pipeline, et l'arbre ne les passe pas (134 et 119 signalements, tous
  antérieurs à cette release : alias `Quantity`, `str, Enum` au lieu de
  `StrEnum`, noms d'arguments normatifs comme `As` ou `M_Ed`). Les mettre au
  vert est un travail à part entière ; tant qu'il n'est pas fait, les inscrire
  dans la CI ne ferait que la rendre rouge en permanence.
