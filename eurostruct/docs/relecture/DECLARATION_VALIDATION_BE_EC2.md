# Déclaration de validation — paramètres belges EC2 (vérification de poutre)

**Ce document consigne une déclaration. Il ne confirme rien.** Aucune valeur
citée ici n'est opposable, et le mode strict continuera de refuser tant que le
chemin d'autorité n'aura pas été parcouru dans une instance, par **deux
ingénieurs distincts et nommés**. Le dépôt n'écrit jamais `confirmed`, et ce
fichier ne fait pas exception.

---

## 1. La déclaration, telle qu'elle a été faite

> « Je suis ingénieur et je valide les registres et paramètres belges présentés
> dans ce lot, y compris les branches conditionnelles de `w_max`. »
>
> « Ma validation concerne les paramètres présentés. La validation d'un projet
> calculé, le fonctionnement sur Supabase réel et les essais CAO gardent chacun
> leurs propres résultats à établir. »
>
> « Le dispositif actuel exige deux personnes distinctes : ma déclaration
> représente mon accord, pas celui d'un second relecteur. »

| | |
|---|---|
| Déclarée par | le titulaire du compte `abdelhakimelmokrefi@gmail.com` |
| Canal | session de développement, conversation du 2026-09-14 |
| Portée revendiquée | les **19** paramètres du dossier de §2, branches comprises |
| Hors portée, dit par le déclarant | un projet calculé, Supabase réel, les essais CAO |

### Ce que cette ligne de déclarant vaut, et ce qu'elle ne vaut pas

Elle identifie **un compte**, pas une personne vérifiée. Le chemin d'autorité
n'accepte pas une adresse : il lit un `sub` dans un jeton signé par
l'émetteur configuré, et c'est cette identité-là — pas celle-ci — qui sera
inscrite dans `normative_rule_decisions`. Tant que la déclaration n'a pas été
rejouée sous ce jeton, elle est une **intention consignée**, rien de plus.

---

## 2. Le dossier exact auquel elle se rapporte

Une déclaration qui dit « les paramètres belges » ne désigne rien : six mois
plus tard, personne ne peut dire quelles valeurs elle couvrait. Celle-ci
désigne un document reproductible.

| | |
|---|---|
| Dossier | [`dossier_validation_BE_poutre.md`](dossier_validation_BE_poutre.md) |
| Empreinte du dossier | `2812b304795a0adbc0b4188afd4879c496f7273cad3537ec267d3bcba85003c8` |
| Registre | `engine/src/eurostruct_engine/ndp/data/be.json` |
| Empreinte du registre | `43cbf4df29ff3db213ff41cbb199749106673b19cc735dd7fad56f81f0f414d5` |
| Annexe | NBN EN 1992-1-1 ANB, 1ʳᵉ éd., août 2010 |
| Exemplaires lus | `795196…37a1` (texte) et `3a1953…dcdd` (rendu du Tab. 7.1N-ANB) |
| Paramètres | 19, dont 4 conditionnels |
| Statut de chacun, dans le dépôt | `pending_verification` |

Reproduire le dossier, octet pour octet, depuis `tools/ndp_import/` :

```
python scripts/composer_dossier_de_validation.py --pays BE --calcul poutre \
    --as-of 2026-09-14
```

L'empreinte porte sur le **contenu** : elle ne bouge pas si seule la date de
lecture change, et elle bouge dès qu'une valeur, une branche, une clause, un
folio ou un exemplaire change. Si elle ne correspond plus, la déclaration ne
porte plus sur le registre en place, et il faut la refaire — c'est
précisément ce que l'empreinte existe pour rendre visible.

### Les quatre paramètres conditionnels, explicitement

La déclaration les nomme, donc ce document les rend en toutes lettres. Ce sont
ceux qu'aucun nombre unique ne résume, et pour lesquels signer « la valeur »
ne voudrait rien dire.

| paramètre | branches | clause | folio |
|---|---|---|---:|
| `w_max` | X0/XC1 = **0,4 mm** ; XC2–XC4/XD/XS = **0,3 mm** | §7.3.1(5), Tab. 7.1N-ANB | 18 |
| `alpha_cc` | flexion + effort normal = **0,85** ; autre = **1,0** | §3.1.6(1)P | 10 |
| `k1_stress_limit` | XD/XF/XS = **0,5** ; autre = **0,6** | §7.2(2) | 17 |
| `K_span_depth` | console 0,4 ; travée simple 1,0 ; travée de rive continue 1,3 ; travée intérieure 1,5 ; plancher-dalle 1,2 | §7.4.2(2), Tab. 7.4N | 18 |

Deux refus explicites accompagnent `w_max`, et font partie de ce qui est
déclaré : les classes **XF et XA n'ont pas de ligne au Tableau 7.1N-ANB**. Le
moteur ne leur attribue pas 0,3 mm par défaut ; il exige une classe XC/XD/XS
associée, ou refuse avec `w_max_sans_ligne`.

---

## 3. Ce qui manque, nommément

Rien de ce qui suit n'est fabriqué par ce dépôt, et rien ne peut l'être.

| | manquant | qui peut le fournir |
|---|---|---|
| **D1** | Nom légal complet du déclarant | le déclarant |
| **D2** | Numéro d'inscription professionnelle (ordre / titre d'ingénieur) et pays de délivrance | le déclarant |
| **D3** | Date de la déclaration au sens réglementaire | le déclarant |
| **D4** | Identifiant du compte authentifié (`sub` du jeton) sous lequel les 19 propositions seront déposées | l'instance, à la connexion |
| **S1** | **Un second ingénieur nommé, distinct du premier** | personne d'autre que lui |
| **S2** | Son identité authentifiée dans la même instance | l'instance |
| **I1** | Une instance avec base d'autorité joignable (`/ready` vert) | l'exploitant |

`D1` à `D3` ne sont pas des formalités : c'est ce qui distingue une
déclaration d'une signature. Ils sont laissés **vides**, pas remplis par
défaut.

`S1` est la contrainte qui ne se contourne pas. PostgreSQL refuse, **par
contrainte de table** et non par vérification applicative, que l'approbateur
soit le proposant — `db/migrations/0014_four_eyes_decisions.sql` :

```sql
constraint decision_two_distinct_principals
  check (approver_id is null or approver_id <> proposer_id)
```

Un `CHECK` s'évalue à chaque écriture, quel que soit l'appelant, et survit à
la réécriture du code appelant. Aucune option de configuration, aucun rôle
d'administration et aucun script du dépôt ne la lève.

---

## 4. Le geste restant, dans l'application

Le parcours existe déjà et il est câblé de bout en bout. Écran **Décisions
d'autorité**, pour **chacun** des 19 paramètres :

| | qui | geste | effet |
|---|---|---|---|
| 0 | A | se connecter | un jeton signé, dont le `sub` sera le proposant |
| 1 | A | choisir le paramètre, saisir la citation relevée **dans l'annexe publiée**, le folio imprimé, et ce qu'il certifie avoir lu | — |
| 2 | A | **Composer le dossier** | le *serveur* fabrique les quatre payloads et leurs empreintes ; le navigateur n'en calcule aucune |
| 3 | A | **1. Proposer** | une décision `proposed`, avec le dossier **gelé** en base ; A reçoit un identifiant |
| 4 | A → B | transmettre l'identifiant | hors application |
| 5 | B | se connecter à **sa propre** session | — |
| 6 | B | **2. Relire le dossier gelé** | B lit ce qui a été proposé, pas un numéro |
| 7 | B | **3. Approuver** | refusé si B = A, par contrainte SQL |
| 8 | A ou B | **4. Consommer** | écrit la confirmation ; rejeu refusé |

Après la 19ᵉ consommation, le bandeau du référentiel bascule de lui-même : la
couverture est relue depuis le provider, et le mode strict part.

### Où lire l'avancement, sans deviner

`GET /v1/ndp/BE/couverture` répond à la question qu'on se pose devant
l'écran — *ce calcul-là peut-il partir, sur cette base-ci ?* — et sépare les
trois faits :

* **transcrit** : ce que le dépôt porte (19/19) ;
* **décidé en base** : ce que cette instance a enregistré ;
* **utilisable** : l'intersection, restreinte à ce que le calcul demande.

Sans base branchée, le troisième compte est **« non interrogé »**, jamais
« zéro » : les deux appellent des gestes opposés.

---

## 5. Ce qui est préparé pour le second regard

Pour que B n'ait pas à refaire le travail de A, et sans qu'aucune identité ne
soit fabriquée :

* le **dossier de §2** est reproductible et son empreinte est publiée : B peut
  vérifier qu'il relit bien ce sur quoi A a déclaré ;
* chaque décision proposée **gèle son dossier en base**, et
  `GET /v1/authority/decisions/{id}` le rend tel quel — les empreintes y sont
  **recalculées sur ce qui est relu**, jamais reprises d'un champ stocké, parce
  qu'une empreinte conservée à côté de son payload s'accorde avec lui par
  construction et ne prouve rien ;
* les deux exemplaires de l'annexe sont désignés par leur empreinte complète,
  donc B peut exiger le bon PDF ;
* les folios imprimés sont cités paramètre par paramètre, donc B ouvre la page,
  il ne cherche pas.

Ce qui n'est **pas** préparé, et ne le sera pas par ce dépôt : l'identité de B,
son compte, et son accord.

---

## 6. Portée : ce que cette déclaration ne couvre pas

Le déclarant l'a écrit lui-même, et c'est repris ici pour que personne ne
l'élargisse plus tard.

1. **Un projet calculé.** Valider des paramètres n'est pas valider une note de
   calcul. Chaque étude garde sa propre validation par un ingénieur nommé, et
   la mention obligatoire reste sur chaque document émis.
2. **Supabase réel.** La compatibilité est implémentée pour PostgreSQL 16 et
   marquée `SUPABASE_UNVERIFIED`. Aucun cycle complet n'a été exécuté sur une
   instance Supabase de staging.
3. **Les essais CAO.** Le DXF est produit par `ezdxf` (licence MIT) en R2018.
   Le DWG natif n'est pas offert — aucune licence ODA/RealDWG n'a été prise.
   Toute compatibilité annoncée devra correspondre à un essai réellement
   effectué.

---

## 7. Pourquoi ce fichier ne peut pas confirmer

Une confirmation, dans ce système, est **une ligne écrite par PostgreSQL au
terme d'une transaction** qui a vérifié : que le proposant était authentifié,
que l'approbateur était quelqu'un d'autre, que le dossier relu était celui qui
avait été gelé, et que la décision n'avait pas déjà été consommée. Elle porte
deux `sub`, deux horodatages serveur, et les empreintes du sujet.

Un fichier Markdown ne porte aucune de ces quatre vérifications. Écrire
`confirmed` ici ne rendrait pas la valeur utilisable — le moteur lit les
confirmations en base, pas le dépôt — mais rendrait le dépôt **menteur**, ce
qui est pire : quelqu'un finirait par croire le fichier.

C'est aussi pourquoi `composer_dossier_de_validation.py` est mesuré sur ce
point : `test_composer_n_ecrit_rien_dans_le_registre` vérifie qu'après
exécution, `be.json` est octet pour octet ce qu'il était.
