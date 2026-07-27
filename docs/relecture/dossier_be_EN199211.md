# Dossier de relecture — NBN EN 1992-1-1 ANB (1e ed., aout 2010)

- Fichier : `aea3d1fd-506913780NBNEN199211ANB2010F.pdf`, 0 pages
- Empreinte SHA-256 : `7951964092a4ad595f4d7ea95bea7e2099ca75d83c669a05561ecafb386b37a1`
- Déposé par : A. El Mokrefi (deposant du fichier, PAS le verificateur)
- Extraction : 0.1.0, le 2026-07-27T10:00:39+00:00

## Ce que vous signez

En renseignant `verified_by`, vous attestez avoir **ouvert ce document
à la page citée** et y avoir lu la valeur que vous inscrivez. Vous
n'attestez pas que la machine a bien lu : elle se trompe souvent, et
le tableau ci-dessous le mesure.

## Fiabilité mesurée de l'extraction automatique

Mesurée uniquement sur les paramètres qu'un humain a déjà ouverts dans
ce document. Ceux qui portent encore la valeur recommandée par l'EN
sont **non jugeables** : personne n'a lu l'annexe à leur sujet, et les
compter fausserait le taux dans un sens comme dans l'autre.

| Verdict | Nombre | Part du jugeable |
|---|---:|---:|
| Concorde avec la lecture humaine | 5 | 28% |
| **Diverge** | 7 | 39% |
| Rien lu | 6 | 33% |
| **Total jugeable** | **18** | |
| Conditionnel — valeurs par cas, à confirmer (hors taux) | 3 | — |
| Sans valeur exploitable (hors taux) | 1 | — |
| Non jugeable, valeur EN par défaut (hors taux) | 6 | — |
| **Total paramètres** | **28** | |

> La machine propose la bonne valeur dans **5 cas sur 18**
> jugeables. Elle se trompe 7 fois. C'est la raison d'être de
> votre signature : aucune de ces propositions n'entre dans le moteur
> sans elle.

## Paramètre par paramètre

| Paramètre | Clause | Machine | p. | Conf. | Lecture main | p. | Verdict |
|---|---|---:|---:|---:|---:|---:|---|
| `As_max_ratio` | §9.2.1.1(3) | — | — | — | 0.04 | 22 | RIEN LU |
| `As_min_coeff` | §9.2.1.1(1), eq. (9.1N) | 2.0 | 22 | 0.55 | 0.26 | 22 | DIVERGE |
| `As_min_floor` | §9.2.1.1(1), eq. (9.1N) | 0.04 | 22 | 0.55 | 0.0013 | 22 | DIVERGE |
| `C_Rd_c_coeff` | §6.2.2(1) | — | — | — | 0.18 | 17 | RIEN LU |
| `alpha_cc` | §3.1.6(1)P | 1.0 | 8 | 0.45 | axial_and_bending = 0.85 ; other = 1 | 10 | CONDITIONNEL |
| `alpha_ct` | §3.1.6(2)P | 1.0 | 20 | 0.55 | 1 | 10 | concorde |
| `alpha_cw` | §6.2.3(3) | — | — | — | 1 | — | NON JUGEABLE |
| `cot_theta_max` | §6.2.3(2), eq. (6.7N) | 2.0 | 17 | 0.45 | — | 17 | NON REPRESENTABLE |
| `cot_theta_min` | §6.2.3(2), eq. (6.7N) | 1.0 | 17 | 0.45 | 1 | 17 | concorde |
| `gamma_C_accidental` | §2.4.2.4(1), Tab. 2.1N | 1.0 | 8 | 0.65 | 1.2 | 8 | DIVERGE |
| `gamma_C_persistent` | §2.4.2.4(1), Tab. 2.1N | 1.5 | 8 | 0.65 | 1.5 | 8 | concorde |
| `gamma_S_accidental` | §2.4.2.4(1), Tab. 2.1N | 1.0 | 8 | 0.65 | 1 | 8 | concorde |
| `gamma_S_persistent` | §2.4.2.4(1), Tab. 2.1N | 1.0 | 8 | 0.65 | 1.15 | 8 | DIVERGE |
| `k1_redistribution` | §5.5(4) | 0.3 | 26 | 0.45 | 0.44 | 15 | DIVERGE |
| `k1_shear` | §6.2.2(1) | 0.15 | 17 | 0.45 | 0.15 | 17 | concorde |
| `k1_stress_limit` | §7.2(2) | — | — | — | XD_XF_XS = 0.5 ; other = 0.6 | 17 | CONDITIONNEL |
| `k2_redistribution` | §5.5(4) | 21.0 | 23 | 0.35 | 1.25 | 15 | DIVERGE |
| `k3_crack_spacing` | §7.3.4(3), eq. (7.11) | — | — | — | 3.4 | 17 | RIEN LU |
| `k3_steel_stress` | §7.2(5) | — | — | — | 0.8 | 17 | RIEN LU |
| `k4_crack_spacing` | §7.3.4(3), eq. (7.11) | — | — | — | 0.425 | 17 | RIEN LU |
| `k4_steel_stress_imposed` | §7.2(5) | — | — | — | 1 | 17 | RIEN LU |
| `nu1_coeff` | §6.2.2(6), eq. (6.6N) | 2.0 | 17 | 0.8 | 0.6 | — | NON JUGEABLE |
| `nu1_fck_divisor` | §6.2.2(6), eq. (6.6N) | 1.0 | 17 | 0.8 | 250 | — | NON JUGEABLE |
| `rho_w_min_coeff` | §9.2.2(5), eq. (9.5N) | 3.0 | 22 | 0.65 | 0.08 | — | NON JUGEABLE |
| `s_l_max_coeff` | §9.2.2(6), eq. (9.6N) | 20.0 | 22 | 0.65 | 0.75 | — | NON JUGEABLE |
| `s_t_max_coeff` | §9.2.2(8), eq. (9.8N) | 2.0 | 23 | 0.65 | 0.75 | — | NON JUGEABLE |
| `v_min_coeff` | §6.2.2(1), eq. (6.3N) | 1.0 | 17 | 0.55 | 0.035 | 17 | DIVERGE |
| `w_max` | §7.3.1(5), Tab. 7.1N | — | — | — | X0_XC1 = 0.4 ; XC2_XC4_XD_XS = 0.3 | 17 | CONDITIONNEL |

## Marche à suivre

1. Ouvrir `decisions_be_EN199211.json`.
2. Pour chaque entrée : ouvrir le document à la page citée, lire la
   valeur, puis renseigner `outcome` (`accepted` / `corrected` /
   `rejected` / `deferred`), `final_value`, `verified_by` (**nom de
   personne**, pas un organisme) et `verified_at` (ISO 8601).
3. Appliquer :

```
ndp-import apply --run run_be_ec2.json --decisions decisions_be_EN199211.json \
    --dataset engine/src/eurostruct_engine/ndp/data/be.json
```

Toute décision sans nom de vérificateur, sans horodatage, sans page ou
sans source officielle est refusée par `to_engine_records`.
