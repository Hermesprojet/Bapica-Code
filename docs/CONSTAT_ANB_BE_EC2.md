# Constat — NBN EN 1992-1-1 ANB, relevé de lecture

> **Ce document n'est pas une source normative.** C'est un compte rendu de
> lecture destiné à faire gagner du temps à l'ingénieur qui relèvera les
> valeurs. Aucune des valeurs ci-dessous n'est encodée dans le moteur : elles
> attendent une confirmation nominative.

## Document

| | |
|---|---|
| Référence | NBN EN 1992-1-1 ANB |
| Édition annoncée | `NBN EN 1992-1-1 ANB:2010 (F)` — **à confirmer par le déposant** |
| Pages | 31, texte natif (50 237 caractères) |
| Langue | français |

Une version scannée du même document (34 pages) avait été déposée auparavant.
La version texte la remplace avantageusement : la ROC ne savait pas lire les
tableaux.

## Le point qui change un résultat — §3.1.6 (1)P, page 10

Texte du document :

> « Pour les vérifications à l'état limite ultime (ELU) de la résistance à
> l'effort normal, la flexion simple ou composée, **la valeur de α_cc vaut
> 0,85**. Pour les autres cas, α_cc vaut 1,0. »

**La Belgique s'écarte de la valeur recommandée par l'Eurocode (1,0).** C'est
précisément le cas que l'interdiction n°3 du cahier des charges vise, et le
jeu de données provisoire du moteur portait 1,0.

### Effet mesuré sur le cas de référence

300 × 600 mm, d = 550 mm, C30/37, B500B, M_Ed = 250 kN·m :

| | α_cc = 1,0 | α_cc = 0,85 | écart |
|---|---|---|---|
| f_cd | 20,00 MPa | 17,00 MPa | **−15,00 %** |
| μ | 0,1377 | 0,1620 | +17,65 % |
| x/d | 0,1860 | 0,2223 | **+19,52 %** |
| z | 509,08 mm | 501,09 mm | −1,57 % |
| A_s requis | 1129,50 mm² | 1147,51 mm² | +1,59 % |

L'écart sur l'acier est modeste ici. Deux conséquences le sont beaucoup moins :

- **x/d monte de 19,5 %.** Sur une section proche de la limite de ductilité,
  cela rapproche du refus.
- **Le moment maximal admissible avant refus baisse de 15 %** : de 534 kN·m à
  454 kN·m sur cette section. Une poutre acceptée avec α_cc = 1,0 peut être
  refusée avec 0,85.

## Les autres paramètres bloquants, tels que lus

Le document déclare **« normatives »** les valeurs recommandées pour :

| Clause | Page | Ce que dit le document |
|---|---|---|
| §2.4.2.4 (1) | 8 | Tableau 2.1N repris : durable/transitoire **γ_C 1,5 · γ_S 1,15** ; accidentelle **γ_C 1,2 · γ_S 1,0** |
| §3.1.6 (2)P | 10 | α_ct = **1,0** |
| §5.5 (4) | 15 | k₁ = **0,44** ; k₂ = **1,25·(0,6+0,0014/ε_cu2)** ; k₃ = 0,54 ; k₄ = idem k₂ ; k₅ = 0,7 ; k₆ = 0,8 |
| §9.2.1.1 (1) | 22 | A_s,min : Formule 9.1N normative |
| §9.2.1.1 (3) | 22 | A_s,max = **0,04·A_c** |
| §6.2.2 (1) | 17 | C_Rd,c = **0,18/γ_C** ; v_min = **0,035·k^{3/2}·f_ck^{1/2}** ; k₁ = **0,15** |

### Un second écart possible, à vérifier — §6.4.4 (1), page 17

Pour le **poinçonnement**, le texte lu mentionne des valeurs différentes de
celles de l'effort tranchant :

> « Les valeurs de C (0,15/γ), v (0,30·k^{3/2}·f^{1/2}) et k (0,15) sont
> normatives »

soit **0,15/γ_C** et **0,30** au lieu de 0,18/γ_C et 0,035. Si cette lecture
est exacte, le poinçonnement suit des coefficients propres. Le moteur ne
traite pas encore le poinçonnement ; à retenir pour quand il le fera.

## Ce qu'il reste à faire

Ouvrir les pages **8, 10, 15, 17 et 22**, vérifier les huit valeurs, puis :

```bash
ndp-import extract --pdf NBNEN199211ANB2010F.pdf --role national_annex \
  --country BE --standard "EN 1992" --part 1-1 \
  --reference "NBN EN 1992-1-1 ANB" --publisher NBN \
  --edition "1e ed., 2010" --effective-from 2010-XX-XX \
  --language fr --deposited-by "<nom de l'ingénieur>" --out run.json

ndp-import review --run run.json          # file de relecture
ndp-import apply  --run run.json --decisions decisions.json \
                  --dataset engine/src/eurostruct_engine/ndp/data/be.json
```

Le passage en `confirmed` exige le nom du relecteur, l'horodatage et le numéro
de page. Le schéma le refuse autrement.
