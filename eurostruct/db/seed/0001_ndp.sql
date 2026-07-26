-- GENERATED FILE — DO NOT EDIT.
--
-- Produced by db/seed/generate_ndp_seed.py from the engine's NDP data.
-- Re-run after changing engine/src/eurostruct_engine/ndp/data/*.json:
--
--     python db/seed/generate_ndp_seed.py > db/seed/0001_ndp.sql
--
-- Statuses are carried across verbatim. A parameter reaches
-- 'na_confirmed' only when an engineer has read the published National
-- Annex and signed for it; the schema refuses that status without a
-- named verifier and a date.

begin;

-- ----- BE — 0.1.0-draft ------------------------------
insert into national_annex_sets (country, region, version, published_at, description)
values ('BE'::country_code, null, '0.1.0-draft', '2026-07-26'::date, 'Belgique — Annexes Nationales NBN EN 199x-x-x ANB. JEU DE DONNEES NON VERIFIE: les valeurs ci-dessous sont les valeurs RECOMMANDEES par l''Eurocode, reportees ici comme point de depart. Chacune doit etre relevee dans l''ANB publiee par le NBN, puis passee au statut ''na_confirmed'' par un ingenieur habilite, avant tout usage en production.')
on conflict (country, region, version) do nothing;

insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.As_max_ratio', 0.04, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§9.2.1.1(3)', 'Section maximale d''armature tendue ou comprimee, hors zones de recouvrement: 0,04 Ac', 'A relever dans NBN EN 1992-1-1 ANB', 0.04
from national_annex_sets s
where s.country = 'BE'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;
insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.As_min_coeff', 0.26, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§9.2.1.1(1), eq. (9.1N)', 'Coefficient de la section minimale d''armature tendue: 0,26 fctm/fyk bt d', 'A relever dans NBN EN 1992-1-1 ANB', 0.26
from national_annex_sets s
where s.country = 'BE'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;
insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.As_min_floor', 0.0013, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§9.2.1.1(1), eq. (9.1N)', 'Plancher de la section minimale d''armature tendue: 0,0013 bt d', 'A relever dans NBN EN 1992-1-1 ANB', 0.0013
from national_annex_sets s
where s.country = 'BE'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;
insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.alpha_cc', 1.0, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§3.1.6(1)P', 'Coefficient tenant compte des effets de longue duree sur la resistance en compression (domaine EN: 0,8 a 1,0)', 'A relever dans NBN EN 1992-1-1 ANB', 1.0
from national_annex_sets s
where s.country = 'BE'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;
insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.alpha_ct', 1.0, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§3.1.6(2)P', 'Coefficient tenant compte des effets de longue duree sur la resistance en traction', 'A relever dans NBN EN 1992-1-1 ANB', 1.0
from national_annex_sets s
where s.country = 'BE'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;
insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.gamma_C.accidental', 1.2, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel du beton — situations accidentelles', 'A relever dans NBN EN 1992-1-1 ANB', 1.2
from national_annex_sets s
where s.country = 'BE'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;
insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.gamma_C.persistent', 1.5, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel du beton — situations durables et transitoires', 'A relever dans NBN EN 1992-1-1 ANB', 1.5
from national_annex_sets s
where s.country = 'BE'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;
insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.gamma_S.accidental', 1.0, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel de l''acier — situations accidentelles', 'A relever dans NBN EN 1992-1-1 ANB', 1.0
from national_annex_sets s
where s.country = 'BE'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;
insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.gamma_S.persistent', 1.15, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel de l''acier de beton arme — situations durables et transitoires', 'A relever dans NBN EN 1992-1-1 ANB', 1.15
from national_annex_sets s
where s.country = 'BE'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;
insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.k1_redistribution', 0.44, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§5.5(4)', 'Coefficient k1 bornant xu/d pour la ductilite (fck <= 50 MPa)', 'A relever dans NBN EN 1992-1-1 ANB', 0.44
from national_annex_sets s
where s.country = 'BE'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;
insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.k2_redistribution', 1.25, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§5.5(4)', 'Coefficient k2 bornant xu/d pour la ductilite. Valeur recommandee EN: 1,25(0,6+0,0014/eps_cu2), soit 1,25 pour eps_cu2 = 3,5 pour mille (fck <= 50 MPa). Au-dela de C50/60 ce parametre doit etre re-exprime.', 'A relever dans NBN EN 1992-1-1 ANB', 1.25
from national_annex_sets s
where s.country = 'BE'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;

-- ----- FR — 0.1.0-draft ------------------------------
insert into national_annex_sets (country, region, version, published_at, description)
values ('FR'::country_code, null, '0.1.0-draft', '2026-07-26'::date, 'France — Annexes Nationales NF EN 199x-x-x/NA (AFNOR). JEU DE DONNEES NON VERIFIE: les valeurs ci-dessous sont les valeurs RECOMMANDEES par l''Eurocode, reportees ici comme point de depart. Chacune doit etre relevee dans la NA publiee par l''AFNOR, puis passee au statut ''na_confirmed'' par un ingenieur habilite, avant tout usage en production.')
on conflict (country, region, version) do nothing;

insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.As_max_ratio', 0.04, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§9.2.1.1(3)', 'Section maximale d''armature tendue ou comprimee, hors zones de recouvrement: 0,04 Ac', 'A relever dans NF EN 1992-1-1/NA', 0.04
from national_annex_sets s
where s.country = 'FR'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;
insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.As_min_coeff', 0.26, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§9.2.1.1(1), eq. (9.1N)', 'Coefficient de la section minimale d''armature tendue: 0,26 fctm/fyk bt d', 'A relever dans NF EN 1992-1-1/NA', 0.26
from national_annex_sets s
where s.country = 'FR'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;
insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.As_min_floor', 0.0013, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§9.2.1.1(1), eq. (9.1N)', 'Plancher de la section minimale d''armature tendue: 0,0013 bt d', 'A relever dans NF EN 1992-1-1/NA', 0.0013
from national_annex_sets s
where s.country = 'FR'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;
insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.alpha_cc', 1.0, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§3.1.6(1)P', 'Coefficient tenant compte des effets de longue duree sur la resistance en compression (domaine EN: 0,8 a 1,0). ATTENTION: la NA francaise assortit ce coefficient de conditions selon la nature de la sollicitation — a relever precisement.', 'A relever dans NF EN 1992-1-1/NA', 1.0
from national_annex_sets s
where s.country = 'FR'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;
insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.alpha_ct', 1.0, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§3.1.6(2)P', 'Coefficient tenant compte des effets de longue duree sur la resistance en traction', 'A relever dans NF EN 1992-1-1/NA', 1.0
from national_annex_sets s
where s.country = 'FR'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;
insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.gamma_C.accidental', 1.2, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel du beton — situations accidentelles', 'A relever dans NF EN 1992-1-1/NA', 1.2
from national_annex_sets s
where s.country = 'FR'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;
insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.gamma_C.persistent', 1.5, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel du beton — situations durables et transitoires', 'A relever dans NF EN 1992-1-1/NA', 1.5
from national_annex_sets s
where s.country = 'FR'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;
insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.gamma_S.accidental', 1.0, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel de l''acier — situations accidentelles', 'A relever dans NF EN 1992-1-1/NA', 1.0
from national_annex_sets s
where s.country = 'FR'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;
insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.gamma_S.persistent', 1.15, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel de l''acier de beton arme — situations durables et transitoires', 'A relever dans NF EN 1992-1-1/NA', 1.15
from national_annex_sets s
where s.country = 'FR'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;
insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.k1_redistribution', 0.44, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§5.5(4)', 'Coefficient k1 bornant xu/d pour la ductilite (fck <= 50 MPa)', 'A relever dans NF EN 1992-1-1/NA', 0.44
from national_annex_sets s
where s.country = 'FR'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;
insert into national_annex_parameters (set_id, key, value, unit, status, standard, clause, description, source, en_recommended)
select s.id, 'EC2.k2_redistribution', 1.25, 'dimensionless', 'na_pending_verification'::ndp_status, 'EN 1992-1-1', '§5.5(4)', 'Coefficient k2 bornant xu/d pour la ductilite. Valeur recommandee EN: 1,25(0,6+0,0014/eps_cu2), soit 1,25 pour eps_cu2 = 3,5 pour mille (fck <= 50 MPa). Au-dela de C50/60 ce parametre doit etre re-exprime.', 'A relever dans NF EN 1992-1-1/NA', 1.25
from national_annex_sets s
where s.country = 'FR'::country_code and s.region is null and s.version = '0.1.0-draft'
on conflict (set_id, key) do nothing;

commit;
