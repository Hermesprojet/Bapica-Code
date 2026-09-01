# Ticket — les paramètres nationaux qui sont des FORMULES

**Statut : ouvert, non planifié. Délibérément hors du lot « vérification
complète d'une poutre ».**

Ce ticket n'est pas une idée d'amélioration : c'est la description d'une
**lacune mesurée**, qui bloque aujourd'hui une vérification réelle pour la
France. Il est écrit maintenant parce que la contourner dans le lot en cours
aurait été une modification normative structurante, et parce qu'une lacune
qu'on ne décrit pas se redécouvre.

---

## 1. Le fait, mesuré

```
preflight_beam(country="FR", as_of=2026-01-01, strict=False)
  → ready = False
  → 1 bloquant  reason = not_representable
                module = serviceability
                paramètre = EN 1992-1-1:k3_crack_spacing
```

La vérification ELS française **ne peut pas s'exécuter**, quel que soit le
mode. L'étude française rend donc quatre sections sur cinq, la cinquième
honnêtement `not_evaluated`.

Ce n'est **pas** un paramètre « non confirmé ». La distinction décide de ce
qu'un ingénieur doit faire :

| | Ce qui débloque |
|---|---|
| `pending_verification` | faire relever la valeur dans l'annexe publiée, puis la confirmer |
| `not_representable` | **changer le modèle** — aucune confirmation n'existe |

Présenter le second comme le premier enverrait quelqu'un chercher une
confirmation qui n'existe pas.

---

## 2. La formule concernée

**Source** — NF EN 1992-1-1/NA, §7.3.4(3), coefficient `k3` de l'espacement
maximal des fissures `s_r,max` (équation (7.11)).

**Texte** — `k3 = 3,4` tant que l'enrobage `c` ne dépasse pas 25 mm ; au-delà :

```
k3 = 3,4 · (25 / c)^(2/3)
```

**Variable** — `c`, l'enrobage des armatures longitudinales, en millimètres.
C'est la seule variable ; elle est déjà une donnée d'entrée de
`CrackControlDetail`.

**Unités** — `c` en mm ; `k3` sans dimension. Le `25` est en mm et n'a de sens
que dans le rapport `25/c`.

**Domaine** — `c > 0`. Pour `c ≤ 25 mm`, la valeur est le scalaire `3,4` : la
formule et le scalaire ne se remplacent donc pas, ils se **branchent**.

---

## 3. Ce que le modèle actuel ne sait pas faire

`NationalParameter` porte `parameter_value` — un **scalaire**. Il n'a aucun
moyen d'exprimer :

- une valeur qui dépend d'une grandeur du calcul ;
- un branchement sur un domaine (`c ≤ 25` / `c > 25`) ;
- les unités de la variable, ni son domaine de validité.

Le registre le dit correctement plutôt que de mentir : le paramètre est marqué
`not_representable`, avec la note qui explique pourquoi. **C'est le bon
comportement actuel**, et il ne doit pas être « corrigé » en substituant la
recommandation EN.

Ce n'est pas un cas isolé. La Belgique a rencontré le même problème sur sept
paramètres de cisaillement et l'a résolu par des **règles typées**
(`be.ec2.cot_theta_max`, `be.ec2.rho_w_min`, …) : les scalaires qu'elles
remplacent sont marqués `deprecated`, refusés dans tous les modes, pour qu'un
seul chemin normatif subsiste par juridiction. **Le mécanisme des règles typées
est donc le précédent à suivre**, pas un mécanisme à inventer.

---

## 4. Ce qui est exigé de l'implémentation

### Représentation typée, jamais d'évaluation arbitraire

**Interdit : tout `eval`, `exec`, ou évaluation d'une chaîne fournie par une
donnée.** Un référentiel normatif n'est pas un langage de programmation. Une
valeur nationale qui pourrait exécuter du code ferait du registre une surface
d'exécution — et rien ne distinguerait alors une annexe d'une charge utile.

La formule doit être un **arbre typé** ou une **fonction nommée enregistrée**,
comme les règles belges : un identifiant de règle résolu dans un registre de
code, dont les arguments sont validés et unités comprises.

### Le contrat minimal

- l'identifiant de la variable, son unité et son domaine sont **déclarés** ;
- une variable hors domaine **refuse**, elle n'extrapole pas ;
- une variable manquante **refuse**, elle ne prend pas de défaut ;
- la règle porte sa clause, son annexe et son édition, comme un scalaire ;
- le journal du calcul reçoit **l'application numérique**, pas seulement le
  résultat : `k3 = 3,4 · (25/40)^(2/3) = 2,50` doit être lisible dans la note ;
- le statut reste soumis à confirmation : une règle transcrite mais non relevée
  bloque en mode strict, exactement comme un scalaire.

---

## 5. Tests attendus

1. `c = 25 mm` → `k3 = 3,4` (la branche scalaire, exactement).
2. `c = 40 mm` → `k3 = 3,4 · (25/40)^(2/3)`, vérifié à la main.
3. `c ≤ 0` → refus, pas de valeur.
4. `c` absent → refus explicite, jamais de défaut substitué.
5. La règle non confirmée bloque en mode strict.
6. La règle confirmée débloque **uniquement** l'édition confirmée.
7. Le scalaire `k3_crack_spacing` devient `deprecated` : plus aucun module ne
   peut le lire — un seul chemin normatif par juridiction.
8. L'ELS français s'exécute alors de bout en bout, et
   `FR_EXPLORATORY_SLS_NOT_EVALUATED_FORMULA_MODEL_GAP` cesse d'être vrai.
9. Aucune chaîne du registre n'atteint un évaluateur : test négatif explicite.
10. La note imprime l'application numérique issue du journal, pas une valeur
    recalculée par le rendu.

---

## 6. Ce que ce ticket ne demande pas

- Aucun relevé de valeur nationale n'est effectué ici. Le registre reste
  honnêtement à **0/29**.
- Aucune substitution de la recommandation EN pour « débloquer » la France.
  Deux fixtures de test le font déjà, explicitement marquées hypothétiques, et
  elles ne doivent pas quitter les tests.
- Aucune promesse de calendrier.

---

*Toute note produite par EUROSTRUCT doit être validée par un ingénieur
habilité avant usage.*
