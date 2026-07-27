-- GENERATED FILE — DO NOT EDIT.
--
-- Produced by db/seed/generate_ndp_seed.py from the engine's NDP data.
-- Re-run after changing engine/src/eurostruct_engine/ndp/data/*.json:
--
--     python db/seed/generate_ndp_seed.py > db/seed/0001_ndp.sql
--
-- Statuses are carried across verbatim. A parameter reaches
-- 'confirmed' only when an engineer has read the published National
-- Annex and signed for it; the schema refuses that status without a
-- named verifier, a date, and source_type = 'national_annex'.

begin;

-- ===== BE — Belgique ==============================

-- NBN EN 1992-1-1 ANB (EN 1992-1-1)
insert into national_annexes (country_code, standard_family, part, reference, edition, effective_from, effective_to, source_official, source_url_or_doc_id)
values ('BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be')
on conflict (country_code, standard_family, part, edition) do nothing;

insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'As_max_ratio', 0.04, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'national_annex'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'LU par le pipeline d''import dans NBN EN 1992-1-1 ANB (1e ed., aout 2010), p. 22. NON CONFIRME par un ingenieur: le mode strict continue de bloquer. Texte releve — §9.2.1.1(3): « La valeur de As,max recommandee (0,04 Ac) est normative. »', '§9.2.1.1(3)', 'Section maximale d''armature tendue ou comprimee, hors recouvrements: 0,04 Ac', 0.04
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'As_min_coeff', 0.26, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'national_annex'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'LU par le pipeline d''import dans NBN EN 1992-1-1 ANB (1e ed., aout 2010), p. 22. NON CONFIRME par un ingenieur: le mode strict continue de bloquer. Texte releve — §9.2.1.1(1): « La valeur de As,min recommandee (Formule 9.1N) est normative. » Formule 9.1N: 0,26 fctm/fyk bt d.', '§9.2.1.1(1), eq. (9.1N)', 'Coefficient de la section minimale d''armature tendue: 0,26 fctm/fyk bt d', 0.26
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'As_min_floor', 0.0013, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'national_annex'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'LU par le pipeline d''import dans NBN EN 1992-1-1 ANB (1e ed., aout 2010), p. 22. NON CONFIRME par un ingenieur: le mode strict continue de bloquer. Texte releve — §9.2.1.1(1), Formule 9.1N: plancher 0,0013 bt d.', '§9.2.1.1(1), eq. (9.1N)', 'Plancher de la section minimale d''armature tendue: 0,0013 bt d', 0.0013
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'C_Rd_c_coeff', 0.18, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'national_annex'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'LU par le pipeline d''import dans NBN EN 1992-1-1 ANB (1e ed., aout 2010), p. 17. NON CONFIRME par un ingenieur: le mode strict continue de bloquer. Texte releve — §6.2.2(1): « Les valeurs recommandees de C_Rd,c (0,18/gamma_C), v_min (0,035 k^3/2 fck^1/2) et k1 (0,15) sont normatives. » ATTENTION: « Pour les dalles appuyees sur les bords, il faut multiplier ces valeurs par 1,25 » — condition non modelisee.', '§6.2.2(1)', 'Coefficient de C_Rd,c = 0,18/gamma_C, resistance a l''effort tranchant sans armatures d''effort tranchant', 0.18
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'alpha_cc', 0.85, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'national_annex'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'LU par le pipeline d''import dans NBN EN 1992-1-1 ANB (1e ed., aout 2010), p. 10. NON CONFIRME par un ingenieur: le mode strict continue de bloquer. Texte releve — §3.1.6(1)P: « Pour les verifications a l''ELU de la resistance a l''effort normal, la flexion simple ou composee, la valeur de alpha_cc vaut 0,85. Pour les autres cas, alpha_cc vaut 1,0. » ECART par rapport a la valeur recommandee EN (1,0). ATTENTION: valeur CONDITIONNELLE — 0,85 en flexion, 1,0 dans les autres cas. Le moteur ne stocke qu''un scalaire et retient 0,85, ce qui est le cas couvert par le module de flexion. Toute extension a d''autres sollicitations devra modeliser la condition.', '§3.1.6(1)P', 'Coefficient tenant compte des effets de longue duree sur la resistance en compression du beton (domaine EN: 0,8 a 1,0)', 1.0
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'alpha_ct', 1.0, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'national_annex'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'LU par le pipeline d''import dans NBN EN 1992-1-1 ANB (1e ed., aout 2010), p. 10. NON CONFIRME par un ingenieur: le mode strict continue de bloquer. Texte releve — §3.1.6(2)P: « La valeur de alpha_ct recommandee (1,0) est normative. »', '§3.1.6(2)P', 'Coefficient tenant compte des effets de longue duree sur la resistance en traction du beton', 1.0
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'alpha_cw', 1.0, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.3(3)', 'Coefficient alpha_cw tenant compte de l''etat de contrainte dans la membrure comprimee. 1,0 pour une structure non precontrainte', 1.0
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'cot_theta_max', null, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'national_annex'::ndp_source_type, 'not_representable'::ndp_validation_status, null, null, 'SANS VALEUR EXPLOITABLE. §6.2.3(2) p.17: la Belgique NE retient PAS la borne 2,5. Elle fixe cot(theta)_max = (2 + k1 sigma_cp bw d s / (Asw z fywd)) <= 3, avec sigma_cp <= 0,2 fcd. C''est une FORMULE dependant de l''effort normal et du ferraillage, pas une constante. Le modele de parametre ne stocke qu''un scalaire: le representer par 2,5 ou par 3 serait faux dans les deux cas. Ce parametre reste sans valeur tant que le modele n''admet pas une expression.', '§6.2.3(2), eq. (6.7N)', 'Borne superieure de cot(theta), inclinaison des bielles', 2.5
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'cot_theta_min', 1.0, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'national_annex'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'LU par le pipeline d''import dans NBN EN 1992-1-1 ANB (1e ed., aout 2010), p. 17. NON CONFIRME par un ingenieur: le mode strict continue de bloquer. Texte releve — §6.2.3(2): « 1,0 <= cot(theta) <= cot(theta)_max ».', '§6.2.3(2), eq. (6.7N)', 'Borne inferieure de cot(theta), inclinaison des bielles', 1.0
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'gamma_C_accidental', 1.2, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'national_annex'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'LU par le pipeline d''import dans NBN EN 1992-1-1 ANB (1e ed., aout 2010), p. 8. NON CONFIRME par un ingenieur: le mode strict continue de bloquer. Texte releve — §2.4.2.4(1), Tableau 2.1N repris: accidentelle, beton 1,2.', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel du beton — situations accidentelles', 1.2
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'gamma_C_persistent', 1.5, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'national_annex'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'LU par le pipeline d''import dans NBN EN 1992-1-1 ANB (1e ed., aout 2010), p. 8. NON CONFIRME par un ingenieur: le mode strict continue de bloquer. Texte releve — §2.4.2.4(1), Tableau 2.1N repris: durable ou transitoire, beton 1,5. Declare « normatives ».', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel du beton — situations durables et transitoires', 1.5
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'gamma_S_accidental', 1.0, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'national_annex'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'LU par le pipeline d''import dans NBN EN 1992-1-1 ANB (1e ed., aout 2010), p. 8. NON CONFIRME par un ingenieur: le mode strict continue de bloquer. Texte releve — §2.4.2.4(1), Tableau 2.1N repris: accidentelle, acier de beton arme 1,0.', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel de l''acier — situations accidentelles', 1.0
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'gamma_S_persistent', 1.15, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'national_annex'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'LU par le pipeline d''import dans NBN EN 1992-1-1 ANB (1e ed., aout 2010), p. 8. NON CONFIRME par un ingenieur: le mode strict continue de bloquer. Texte releve — §2.4.2.4(1), Tableau 2.1N repris: durable ou transitoire, acier de beton arme 1,15.', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel de l''acier de beton arme — situations durables et transitoires', 1.15
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'k1_redistribution', 0.44, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'national_annex'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'LU par le pipeline d''import dans NBN EN 1992-1-1 ANB (1e ed., aout 2010), p. 15. NON CONFIRME par un ingenieur: le mode strict continue de bloquer. Texte releve — §5.5(4): « Les valeurs recommandees (k1 = 0,44 ; k2 = 1,25(0,6+0,0014/eps_cu2) ; k3 = 0,54 ; k4 = idem ; k5 = 0,7 et k6 = 0,8) sont normatives. »', '§5.5(4)', 'Coefficient k1 bornant xu/d pour la ductilite (fck <= 50 MPa)', 0.44
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'k1_shear', 0.15, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'national_annex'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'LU par le pipeline d''import dans NBN EN 1992-1-1 ANB (1e ed., aout 2010), p. 17. NON CONFIRME par un ingenieur: le mode strict continue de bloquer. Texte releve — §6.2.2(1): k1 = 0,15.', '§6.2.2(1)', 'Coefficient k1 de la contribution de l''effort normal a V_Rd,c', 0.15
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'k2_redistribution', 1.25, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'national_annex'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'LU par le pipeline d''import dans NBN EN 1992-1-1 ANB (1e ed., aout 2010), p. 15. NON CONFIRME par un ingenieur: le mode strict continue de bloquer. Texte releve — §5.5(4): k2 = 1,25(0,6+0,0014/eps_cu2), soit 1,25 pour eps_cu2 = 3,5 pour mille (fck <= 50 MPa).', '§5.5(4)', 'Coefficient k2 bornant xu/d pour la ductilite. Recommandation EN: 1,25(0,6+0,0014/eps_cu2), soit 1,25 pour eps_cu2 = 3,5 pour mille (fck <= 50 MPa). Au-dela de C50/60 ce parametre doit etre re-exprime.', 1.25
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'nu1_coeff', 0.6, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.2(6), eq. (6.6N)', 'Coefficient nu de la resistance du beton fissure a l''effort tranchant: nu = 0,6 [1 - fck/250]', 0.6
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'nu1_fck_divisor', 250.0, 'MPa', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.2(6), eq. (6.6N)', 'Diviseur de fck dans nu = 0,6 [1 - fck/250]', 250.0
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'rho_w_min_coeff', 0.08, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.2(5), eq. (9.5N)', 'Coefficient du taux minimal d''armatures d''effort tranchant: rho_w,min = 0,08 sqrt(fck)/fyk', 0.08
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 's_l_max_coeff', 0.75, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.2(6), eq. (9.6N)', 'Coefficient de l''espacement longitudinal maximal des cadres: s_l,max = 0,75 d (1 + cot alpha)', 0.75
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 's_t_max_coeff', 0.75, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.2(8), eq. (9.8N)', 'Coefficient de l''espacement transversal maximal des brins: s_t,max = 0,75 d <= 600 mm', 0.75
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'BE'::country_code, 'EN 1992', '1-1', 'NBN EN 1992-1-1 ANB', '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)', '2010-08-01'::date, null, 'v_min_coeff', 0.035, 'dimensionless', 'NBN — Bureau de Normalisation / Bureau voor Normalisatie', 'https://www.nbn.be', 'national_annex'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'LU par le pipeline d''import dans NBN EN 1992-1-1 ANB (1e ed., aout 2010), p. 17. NON CONFIRME par un ingenieur: le mode strict continue de bloquer. Texte releve — §6.2.2(1): v_min = 0,035 k^3/2 fck^1/2.', '§6.2.2(1), eq. (6.3N)', 'Coefficient de v_min = 0,035 k^(3/2) fck^(1/2)', 0.035
from national_annexes a
where a.country_code = 'BE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = '1e ed., aout 2010 (LUE sur la page de garde, A DECLARER)'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;

-- ===== DE — Allemagne ==============================

-- DIN EN 1992-1-1/NA (EN 1992-1-1)
insert into national_annexes (country_code, standard_family, part, reference, edition, effective_from, effective_to, source_official, source_url_or_doc_id)
values ('DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'DIN — Deutsches Institut fur Normung', 'https://www.din.de')
on conflict (country_code, standard_family, part, edition) do nothing;

insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'As_max_ratio', 0.04, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.1.1(3)', 'Section maximale d''armature tendue ou comprimee, hors recouvrements: 0,04 Ac', 0.04
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'As_min_coeff', 0.26, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.1.1(1), eq. (9.1N)', 'Coefficient de la section minimale d''armature tendue: 0,26 fctm/fyk bt d', 0.26
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'As_min_floor', 0.0013, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.1.1(1), eq. (9.1N)', 'Plancher de la section minimale d''armature tendue: 0,0013 bt d', 0.0013
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'C_Rd_c_coeff', 0.18, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.2(1)', 'Coefficient de C_Rd,c = 0,18/gamma_C, resistance a l''effort tranchant sans armatures d''effort tranchant', 0.18
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'alpha_cc', 1.0, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§3.1.6(1)P', 'Coefficient tenant compte des effets de longue duree sur la resistance en compression du beton (domaine EN: 0,8 a 1,0)', 1.0
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'alpha_ct', 1.0, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§3.1.6(2)P', 'Coefficient tenant compte des effets de longue duree sur la resistance en traction du beton', 1.0
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'alpha_cw', 1.0, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.3(3)', 'Coefficient alpha_cw tenant compte de l''etat de contrainte dans la membrure comprimee. 1,0 pour une structure non precontrainte', 1.0
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'cot_theta_max', 2.5, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.3(2), eq. (6.7N)', 'Borne superieure de cot(theta), inclinaison des bielles', 2.5
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'cot_theta_min', 1.0, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.3(2), eq. (6.7N)', 'Borne inferieure de cot(theta), inclinaison des bielles', 1.0
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'gamma_C_accidental', 1.2, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel du beton — situations accidentelles', 1.2
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'gamma_C_persistent', 1.5, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel du beton — situations durables et transitoires', 1.5
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'gamma_S_accidental', 1.0, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel de l''acier — situations accidentelles', 1.0
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'gamma_S_persistent', 1.15, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel de l''acier de beton arme — situations durables et transitoires', 1.15
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'k1_redistribution', 0.44, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§5.5(4)', 'Coefficient k1 bornant xu/d pour la ductilite (fck <= 50 MPa)', 0.44
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'k1_shear', 0.15, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.2(1)', 'Coefficient k1 de la contribution de l''effort normal a V_Rd,c', 0.15
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'k2_redistribution', 1.25, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§5.5(4)', 'Coefficient k2 bornant xu/d pour la ductilite. Recommandation EN: 1,25(0,6+0,0014/eps_cu2), soit 1,25 pour eps_cu2 = 3,5 pour mille (fck <= 50 MPa). Au-dela de C50/60 ce parametre doit etre re-exprime.', 1.25
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'nu1_coeff', 0.6, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.2(6), eq. (6.6N)', 'Coefficient nu de la resistance du beton fissure a l''effort tranchant: nu = 0,6 [1 - fck/250]', 0.6
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'nu1_fck_divisor', 250.0, 'MPa', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.2(6), eq. (6.6N)', 'Diviseur de fck dans nu = 0,6 [1 - fck/250]', 250.0
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'rho_w_min_coeff', 0.08, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.2(5), eq. (9.5N)', 'Coefficient du taux minimal d''armatures d''effort tranchant: rho_w,min = 0,08 sqrt(fck)/fyk', 0.08
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 's_l_max_coeff', 0.75, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.2(6), eq. (9.6N)', 'Coefficient de l''espacement longitudinal maximal des cadres: s_l,max = 0,75 d (1 + cot alpha)', 0.75
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 's_t_max_coeff', 0.75, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.2(8), eq. (9.8N)', 'Coefficient de l''espacement transversal maximal des brins: s_t,max = 0,75 d <= 600 mm', 0.75
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'DE'::country_code, 'EN 1992', '1-1', 'DIN EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'v_min_coeff', 0.035, 'dimensionless', 'DIN — Deutsches Institut fur Normung', 'https://www.din.de', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.2(1), eq. (6.3N)', 'Coefficient de v_min = 0,035 k^(3/2) fck^(1/2)', 0.035
from national_annexes a
where a.country_code = 'DE'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;

-- ===== ES — Espagne ==============================

-- UNE-EN 1992-1-1 AN (EN 1992-1-1)
insert into national_annexes (country_code, standard_family, part, reference, edition, effective_from, effective_to, source_official, source_url_or_doc_id)
values ('ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org')
on conflict (country_code, standard_family, part, edition) do nothing;

insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'As_max_ratio', 0.04, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.1.1(3)', 'Section maximale d''armature tendue ou comprimee, hors recouvrements: 0,04 Ac', 0.04
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'As_min_coeff', 0.26, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.1.1(1), eq. (9.1N)', 'Coefficient de la section minimale d''armature tendue: 0,26 fctm/fyk bt d', 0.26
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'As_min_floor', 0.0013, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.1.1(1), eq. (9.1N)', 'Plancher de la section minimale d''armature tendue: 0,0013 bt d', 0.0013
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'C_Rd_c_coeff', 0.18, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.2(1)', 'Coefficient de C_Rd,c = 0,18/gamma_C, resistance a l''effort tranchant sans armatures d''effort tranchant', 0.18
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'alpha_cc', 1.0, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§3.1.6(1)P', 'Coefficient tenant compte des effets de longue duree sur la resistance en compression du beton (domaine EN: 0,8 a 1,0)', 1.0
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'alpha_ct', 1.0, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§3.1.6(2)P', 'Coefficient tenant compte des effets de longue duree sur la resistance en traction du beton', 1.0
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'alpha_cw', 1.0, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.3(3)', 'Coefficient alpha_cw tenant compte de l''etat de contrainte dans la membrure comprimee. 1,0 pour une structure non precontrainte', 1.0
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'cot_theta_max', 2.5, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.3(2), eq. (6.7N)', 'Borne superieure de cot(theta), inclinaison des bielles', 2.5
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'cot_theta_min', 1.0, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.3(2), eq. (6.7N)', 'Borne inferieure de cot(theta), inclinaison des bielles', 1.0
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'gamma_C_accidental', 1.2, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel du beton — situations accidentelles', 1.2
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'gamma_C_persistent', 1.5, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel du beton — situations durables et transitoires', 1.5
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'gamma_S_accidental', 1.0, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel de l''acier — situations accidentelles', 1.0
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'gamma_S_persistent', 1.15, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel de l''acier de beton arme — situations durables et transitoires', 1.15
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'k1_redistribution', 0.44, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§5.5(4)', 'Coefficient k1 bornant xu/d pour la ductilite (fck <= 50 MPa)', 0.44
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'k1_shear', 0.15, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.2(1)', 'Coefficient k1 de la contribution de l''effort normal a V_Rd,c', 0.15
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'k2_redistribution', 1.25, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§5.5(4)', 'Coefficient k2 bornant xu/d pour la ductilite. Recommandation EN: 1,25(0,6+0,0014/eps_cu2), soit 1,25 pour eps_cu2 = 3,5 pour mille (fck <= 50 MPa). Au-dela de C50/60 ce parametre doit etre re-exprime.', 1.25
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'nu1_coeff', 0.6, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.2(6), eq. (6.6N)', 'Coefficient nu de la resistance du beton fissure a l''effort tranchant: nu = 0,6 [1 - fck/250]', 0.6
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'nu1_fck_divisor', 250.0, 'MPa', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.2(6), eq. (6.6N)', 'Diviseur de fck dans nu = 0,6 [1 - fck/250]', 250.0
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'rho_w_min_coeff', 0.08, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.2(5), eq. (9.5N)', 'Coefficient du taux minimal d''armatures d''effort tranchant: rho_w,min = 0,08 sqrt(fck)/fyk', 0.08
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 's_l_max_coeff', 0.75, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.2(6), eq. (9.6N)', 'Coefficient de l''espacement longitudinal maximal des cadres: s_l,max = 0,75 d (1 + cot alpha)', 0.75
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 's_t_max_coeff', 0.75, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.2(8), eq. (9.8N)', 'Coefficient de l''espacement transversal maximal des brins: s_t,max = 0,75 d <= 600 mm', 0.75
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'ES'::country_code, 'EN 1992', '1-1', 'UNE-EN 1992-1-1 AN', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'v_min_coeff', 0.035, 'dimensionless', 'AENOR / UNE — Asociacion Espanola de Normalizacion', 'https://www.une.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.2(1), eq. (6.3N)', 'Coefficient de v_min = 0,035 k^(3/2) fck^(1/2)', 0.035
from national_annexes a
where a.country_code = 'ES'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;

-- ===== FR — France ==============================

-- NF EN 1992-1-1/NA (EN 1992-1-1)
insert into national_annexes (country_code, standard_family, part, reference, edition, effective_from, effective_to, source_official, source_url_or_doc_id)
values ('FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org')
on conflict (country_code, standard_family, part, edition) do nothing;

insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'As_max_ratio', 0.04, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.1.1(3)', 'Section maximale d''armature tendue ou comprimee, hors recouvrements: 0,04 Ac', 0.04
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'As_min_coeff', 0.26, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.1.1(1), eq. (9.1N)', 'Coefficient de la section minimale d''armature tendue: 0,26 fctm/fyk bt d', 0.26
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'As_min_floor', 0.0013, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.1.1(1), eq. (9.1N)', 'Plancher de la section minimale d''armature tendue: 0,0013 bt d', 0.0013
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'C_Rd_c_coeff', 0.18, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.2(1)', 'Coefficient de C_Rd,c = 0,18/gamma_C, resistance a l''effort tranchant sans armatures d''effort tranchant', 0.18
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'alpha_cc', 1.0, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§3.1.6(1)P', 'Coefficient tenant compte des effets de longue duree sur la resistance en compression du beton (domaine EN: 0,8 a 1,0)', 1.0
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'alpha_ct', 1.0, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§3.1.6(2)P', 'Coefficient tenant compte des effets de longue duree sur la resistance en traction du beton', 1.0
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'alpha_cw', 1.0, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.3(3)', 'Coefficient alpha_cw tenant compte de l''etat de contrainte dans la membrure comprimee. 1,0 pour une structure non precontrainte', 1.0
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'cot_theta_max', 2.5, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.3(2), eq. (6.7N)', 'Borne superieure de cot(theta), inclinaison des bielles', 2.5
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'cot_theta_min', 1.0, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.3(2), eq. (6.7N)', 'Borne inferieure de cot(theta), inclinaison des bielles', 1.0
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'gamma_C_accidental', 1.2, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel du beton — situations accidentelles', 1.2
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'gamma_C_persistent', 1.5, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel du beton — situations durables et transitoires', 1.5
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'gamma_S_accidental', 1.0, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel de l''acier — situations accidentelles', 1.0
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'gamma_S_persistent', 1.15, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§2.4.2.4(1), Tab. 2.1N', 'Coefficient partiel de l''acier de beton arme — situations durables et transitoires', 1.15
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'k1_redistribution', 0.44, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§5.5(4)', 'Coefficient k1 bornant xu/d pour la ductilite (fck <= 50 MPa)', 0.44
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'k1_shear', 0.15, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.2(1)', 'Coefficient k1 de la contribution de l''effort normal a V_Rd,c', 0.15
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'k2_redistribution', 1.25, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§5.5(4)', 'Coefficient k2 bornant xu/d pour la ductilite. Recommandation EN: 1,25(0,6+0,0014/eps_cu2), soit 1,25 pour eps_cu2 = 3,5 pour mille (fck <= 50 MPa). Au-dela de C50/60 ce parametre doit etre re-exprime.', 1.25
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'nu1_coeff', 0.6, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.2(6), eq. (6.6N)', 'Coefficient nu de la resistance du beton fissure a l''effort tranchant: nu = 0,6 [1 - fck/250]', 0.6
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'nu1_fck_divisor', 250.0, 'MPa', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.2(6), eq. (6.6N)', 'Diviseur de fck dans nu = 0,6 [1 - fck/250]', 250.0
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'rho_w_min_coeff', 0.08, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.2(5), eq. (9.5N)', 'Coefficient du taux minimal d''armatures d''effort tranchant: rho_w,min = 0,08 sqrt(fck)/fyk', 0.08
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 's_l_max_coeff', 0.75, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.2(6), eq. (9.6N)', 'Coefficient de l''espacement longitudinal maximal des cadres: s_l,max = 0,75 d (1 + cot alpha)', 0.75
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 's_t_max_coeff', 0.75, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§9.2.2(8), eq. (9.8N)', 'Coefficient de l''espacement transversal maximal des brins: s_t,max = 0,75 d <= 600 mm', 0.75
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;
insert into national_annex_parameters (annex_id, country_code, standard_family, part, national_annex_reference, edition, effective_from, effective_to, parameter_name, parameter_value, unit, source_official, source_url_or_doc_id, source_type, validation_status, verified_at, verified_by, notes, clause, description, en_recommended)
select a.id, 'FR'::country_code, 'EN 1992', '1-1', 'NF EN 1992-1-1/NA', 'NON RELEVE — edition reelle a renseigner', '2026-07-26'::date, null, 'v_min_coeff', 0.035, 'dimensionless', 'AFNOR — Association francaise de normalisation', 'https://www.afnor.org', 'en_recommended'::ndp_source_type, 'pending_verification'::ndp_validation_status, null, null, 'Valeur RECOMMANDEE par l''Eurocode, reportee comme point de depart. A relever dans l''Annexe Nationale publiee, puis passer validation_status a ''confirmed'' avec verified_by et verified_at.', '§6.2.2(1), eq. (6.3N)', 'Coefficient de v_min = 0,035 k^(3/2) fck^(1/2)', 0.035
from national_annexes a
where a.country_code = 'FR'::country_code
  and a.standard_family = 'EN 1992'
  and a.part = '1-1'
  and a.edition = 'NON RELEVE — edition reelle a renseigner'
on conflict (country_code, standard_family, part, parameter_name, effective_from) do nothing;

commit;
