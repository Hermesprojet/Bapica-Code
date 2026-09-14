# Dossier de validation — BE / poutre

- Registre : `engine/src/eurostruct_engine/ndp/data/be.json`
- Empreinte du registre : `43cbf4df29ff3db213ff41cbb199749106673b19cc735dd7fad56f81f0f414d5`
- Empreinte de ce dossier : `2812b304795a0adbc0b4188afd4879c496f7273cad3537ec267d3bcba85003c8`
- Lu avec `as_of` = 2026-09-14 *(hors empreinte : date de sélection, pas clause du dossier)*
- Paramètres : **19**

Reproduire ce document, octet pour octet, depuis `tools/ndp_import/` :

```
python scripts/composer_dossier_de_validation.py --pays BE --calcul poutre --as-of 2026-09-14
```

> Ce document LISTE ce sur quoi une validation porterait. Il ne confirme rien. Aucune valeur ci-dessous n'est opposable tant qu'elle n'a pas ete proposee, approuvee par un SECOND ingenieur nomme, et consommee par le chemin d'autorite.

| paramètre | valeur ou branches | unité | clause | annexe | folio |
|---|---|---|---|---|---:|
| `As_max_ratio` | 0.04 | dimensionless | §9.2.1.1(3) | NBN EN 1992-1-1 ANB | 22 |
| `As_min_coeff` | 0.26 | dimensionless | §9.2.1.1(1), eq. (9.1N) | NBN EN 1992-1-1 ANB | 22 |
| `As_min_floor` | 0.0013 | dimensionless | §9.2.1.1(1), eq. (9.1N) | NBN EN 1992-1-1 ANB | 22 |
| `C_Rd_c_coeff` | 0.18 | dimensionless | §6.2.2(1) | NBN EN 1992-1-1 ANB | 17 |
| `K_span_depth` | cantilever = 0.4 ; end_span_continuous = 1.3 ; flat_slab = 1.2 ; interior_span_continuous = 1.5 ; simply_supported = 1 | dimensionless | §7.4.2(2), Tab. 7.4N | NBN EN 1992-1-1 ANB | 18 |
| `alpha_cc` | axial_and_bending = 0.85 ; other = 1 | dimensionless | §3.1.6(1)P | NBN EN 1992-1-1 ANB | 10 |
| `alpha_ct` | 1 | dimensionless | §3.1.6(2)P | NBN EN 1992-1-1 ANB | 10 |
| `cot_theta_min` | 1 | dimensionless | §6.2.3(2), eq. (6.7N) | NBN EN 1992-1-1 ANB | 17 |
| `gamma_C_persistent` | 1.5 | dimensionless | §2.4.2.4(1), Tab. 2.1N | NBN EN 1992-1-1 ANB | 8 |
| `gamma_S_persistent` | 1.15 | dimensionless | §2.4.2.4(1), Tab. 2.1N | NBN EN 1992-1-1 ANB | 8 |
| `k1_redistribution` | 0.44 | dimensionless | §5.5(4) | NBN EN 1992-1-1 ANB | 15 |
| `k1_shear` | 0.15 | dimensionless | §6.2.2(1) | NBN EN 1992-1-1 ANB | 17 |
| `k1_stress_limit` | XD_XF_XS = 0.5 ; other = 0.6 | dimensionless | §7.2(2) | NBN EN 1992-1-1 ANB | 17 |
| `k2_redistribution` | 1.25 | dimensionless | §5.5(4) | NBN EN 1992-1-1 ANB | 15 |
| `k3_crack_spacing` | 3.4 | dimensionless | §7.3.4(3), eq. (7.11) | NBN EN 1992-1-1 ANB | 17 |
| `k3_steel_stress` | 0.8 | dimensionless | §7.2(5) | NBN EN 1992-1-1 ANB | 17 |
| `k4_crack_spacing` | 0.425 | dimensionless | §7.3.4(3), eq. (7.11) | NBN EN 1992-1-1 ANB | 17 |
| `v_min_coeff` | 0.035 | dimensionless | §6.2.2(1), eq. (6.3N) | NBN EN 1992-1-1 ANB | 17 |
| `w_max` | X0_XC1 = 0.4 ; XC2_XC4_XD_XS = 0.3 | mm | §7.3.1(5), Tab. 7.1N-ANB | NBN EN 1992-1-1 ANB | 18 |

## Sources

Éditions citées : `1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)`

Documents lus (SHA-256) :

- `3a19536221aef69b16435b88bc05d7aee05cebe823e98cb292e49e48fe68dcdd`
- `7951964092a4ad595f4d7ea95bea7e2099ca75d83c669a05561ecafb386b37a1`

Provenance des valeurs : `national_annex`

Statut dans le dépôt : `pending_verification`

