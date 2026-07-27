# Constat de lecture — Annexes Nationales belges EN 1993 (acier)

Documents lus : `NBN EN 1993-1-1 ANB` (1ʳᵉ éd., décembre 2010, 53 p., français)
et `NBN EN 1993-1-2 ANB` (1ʳᵉ éd., décembre 2010, 17 p., français). Publication
autorisée le 19 mai 2010 pour les deux.

**Aucun paramètre n'est entré dans le moteur.** Ce document dit ce que les deux
annexes contiennent, et surtout ce qu'elles ne suffisent pas à établir.

---

## 1. Le blocage principal : γ_M0, γ_M1, γ_M2 sont hors d'atteinte

L'ANB 1-1 §6.1(1)B, page 19, dit exactement ceci :

> « Les valeurs recommandées sont normatives. »

Elle **ne les imprime pas**. Les valeurs recommandées de γ_M0, γ_M1 et γ_M2
figurent dans la norme de base `NBN EN 1993-1-1:2005` §6.1, qui n'a pas été
déposée. Les inscrire de mémoire serait exactement l'interdiction 2 : une
valeur sans source traçable.

J'ai cherché dans les onze documents EN 1993 déposés (parties 1-2, 1-5, 1-9,
1-10, 1-11 et les ANB). Seule l'EN 1993-1-5 mentionne γ_M0 et γ_M1 — mais
uniquement **comme symboles dans des formules** (§4.14, 5.1, 5.2, 6.1, 6.14),
jamais avec une valeur. L'ANB 1-1 elle-même n'a des γ_M1 qu'à l'intérieur des
formules d'interaction de son annexe C (p. 24 et 27).

> **Document manquant, nommément :** `NBN EN 1993-1-1:2005`, 2ᵉ éd., octobre
> 2005, §6.1 — la seule source qui porte les trois coefficients partiels.

### Une conditionnalité de plus, en §6.1(1)

> « Pour les structures non reprises dans les NBN EN 1993 Partie 2 à Partie 6,
> il convient au client de fournir les valeurs des coefficients partiels γ_Mi.
> Si aucune valeur n'est donnée par le client, les valeurs recommandées sont
> normatives. »

Le **maître d'ouvrage peut donc imposer d'autres γ_Mi**. Un scalaire figé dans
la base ne peut pas représenter ça : la valeur dépend du projet. Il faudra un
mécanisme de surcharge par projet, tracé et signé, avant de calculer de l'acier
en Belgique.

Par contraste, l'ANB 1-2 est explicite en page 5 : *« Tous les NDP sont fixés
par la présente ANB »*. Aucun choix laissé au projet. Les deux annexes n'ont
pas le même régime, et le moteur devra le savoir.

---

## 2. Ce que l'ANB 1-1 fixe elle-même

Sept valeurs sont imprimées dans le document, avec leur page :

| Paramètre | Valeur | Page | Clause |
|---|---|---|---|
| `alpha_cr` (borne inf., analyse plastique) | 10 | 18 | §5.2.1(3) |
| `k` (imperfections d'éléments) | 0,5 | 18 | §5.3.4(3) |
| `λ_LT,0` | 0,2 **ou** 0,4 | 19 | §6.3.2.3(1) |
| `β` (déversement) | 1,0 **ou** 0,75 | 19 | §6.3.2.3(1) |
| `λ_c,0` | 0,5 | 20 | §6.3.2.4(1)B |
| `k_fl` | 1,10 | 20 | §6.3.2.4(2)B |
| température min. de service | 0 °C | 17 | §3.2.3(1) |

Deux réserves :

- **`λ_LT,0` et `β` forment un couple conditionnel.** 0,2 / 1,0 si M_cr est
  calculé sur la section brute ; 0,4 / 0,75 pour les poutres de bâtiments avec
  maintiens, *à condition que les maintiens soient totalement ignorés* pour la
  détermination de M_cr. Deux scalaires indépendants ne peuvent pas porter
  cette règle — même problème structurel que `cot θ_max` en béton armé.
- **`alpha_cr` = 10 semble s'écarter de la recommandation EN (15 pour l'analyse
  plastique).** Je ne peux pas le confirmer sans la base, non détenue. À
  vérifier, pas à affirmer.

## 3. Ce qui n'est pas un nombre du tout

- **§6.3.3(5) : « La méthode 1 est normative. »** L'annexe A de la
  NBN EN 1993-1-1:2005 est normative en Belgique ; l'annexe B **« n'est pas
  d'application en Belgique »** (p. 21). Un moteur qui implémenterait la
  méthode 2 serait hors réglementation belge. Ce n'est pas un paramètre : c'est
  un choix d'algorithme.
- **Les annexes C à G ANB définissent des méthodes belges propres** pour M_cr,
  N_cr / N_cr,T / N_cr,TF, L_cr et λ_LT. Elles n'existent pas dans l'EN. Être
  conforme en Belgique demande de les **implémenter**, pas seulement de
  paramétrer l'Eurocode. C'est un coût de développement, pas un coût
  d'acquisition documentaire.
- §3.2.1(1) : l'option « a » est normative. §5.3.2(3) et §3.2.4(1) renvoient à
  des tableaux entiers de la base.

---

## 4. ANB 1-2 (feu) : le filigrane rend les tableaux illisibles

Cinq valeurs sont lisibles en prose :

| Paramètre | Valeur | Page | Clause |
|---|---|---|---|
| `γ_M,fi` | 1,0 | 6 | §2.3(1) et §2.3(2) |
| `θ_crit` (Classe 4) | 350 °C | 9 | §4.2.3.6(1) |
| `θ_crit` (poutres isostatiques, tirants) | 540 °C | 9 | §4.2.4(2) |
| `θ_crit` (poutres hyperstatiques) | 570 °C | 9 | §4.2.4(2) |
| `θ_crit` (comprimés, flexion-compression) | 500 °C | 9 | §4.2.4(2) |

Mais le document porte un **filigrane vertical « NATIONAL MIRROR COMMITTEE »**
dont les lettres s'intercalent *à l'intérieur des nombres* :

| extrait | valeur réelle probable |
|---|---|
| `5E61` | 561 |
| `4M57` | 457 |
| `R722` | 722 |
| `M160` | 160 |

**« 5E61 » peut être 561 ou 5610. Aucune règle ne permet de trancher**, et
trancher est précisément ce que ce pipeline existe pour empêcher. Sont donc
inexploitables automatiquement :

- **Tableaux 4.1a à 4.1e ANB** (p. 11–15) — températures critiques des colonnes
  comprimées, S235 à S460, selon l'élancement et le taux d'utilisation ;
- **Tableau 4.5 ANB** (p. 16) — température de l'acier après 30 min de feu
  normalisé ;
- **Tableau 4.5 ANB** (p. 8) — limites de λ_LT,θ,com : ici le tableau est en
  plus une **image**, sans aucun texte extractible ;
- **Tableau 4.4 ANB** (p. 7) — k_c = 0,6 + 0,3ψ + 0,15ψ², une formule.

### Défense ajoutée au pipeline

L'extracteur détecte maintenant ce type de filigrane par sa **forme** — un
tampon vertical laisse une colonne de lignes d'une seule majuscule — et non par
son libellé, donc la garde vaut pour n'importe quel éditeur.

- Seuil : 8 lignes d'une seule majuscule par page. Mesuré : ANB 1-2 → jusqu'à
  24 par page, 282 au total ; ANB 1-1 → 6 au maximum (des indices isolés sur
  des pages de formules), donc non signalée ; ANB 1-1-1 béton → 0.
- Une page signalée ne produit **aucun** candidat.
- Les pages écartées sont listées dans `pages_skipped_overlay` et affichées
  dans la file de relecture, avec l'avertissement que « non trouvé » ne veut
  pas dire « absent de l'annexe ». Un écart silencieux serait pire que le
  filigrane.

---

## 5. Défaut corrigé dans le triage

`EN 1993-1-10` et `EN 1993-1-11` étaient annoncés **« EN 1993-1 »** — une partie
qui n'existe pas. Le quantificateur de la partie n'acceptait qu'un chiffre :
sur `1-10`, faute de frontière de mot après le premier `1`, la regex refluait
sur `EN 1993-1`. Conséquence concrète : un dépôt d'EN 1993-1-10 — celui auquel
l'ANB acier renvoie justement en §3.2.3(3) — sortait sous une référence fausse,
puis était écarté comme « hors périmètre ».

Corrigé, avec six cas de non-régression couvrant les parties à un et deux
chiffres.

---

## 6. Ce qu'il faut pour débloquer l'acier belge

Par ordre de blocage :

1. **`NBN EN 1993-1-1:2005` §6.1** — γ_M0, γ_M1, γ_M2. Sans ce document, aucun
   calcul acier n'est possible, quelle que soit la qualité de l'ANB.
2. **Relecture humaine des tableaux 4.1a–4.1e et 4.5 ANB** sur le document
   original (papier ou PDF non filigrané). L'automatisation est exclue ici,
   définitivement.
3. **Un ingénieur nommé** pour confirmer les valeurs lisibles — même exigence
   qu'en béton armé, et pour la même raison : NBN édite la norme, il ne vérifie
   pas une étude.
4. **Un mécanisme de surcharge par projet** pour les γ_Mi que le client peut
   imposer (§6.1(1)).
5. **L'implémentation des annexes C à G ANB**, qui n'ont pas d'équivalent EN.

`NBN EN 1993-1-8 ANB` (assemblages) a été déposée mais est **numérisée**
(9 pages, aucune couche de texte) : elle demande une ROC, dont j'ai déjà mesuré
qu'elle est bonne pour la navigation et inutilisable pour les valeurs de
tableau.
