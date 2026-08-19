-- =====================================================================
-- EUROSTRUCT — 0007: un parametre national peut n'avoir aucune valeur
--
-- NBN EN 1992-1-1 ANB §6.2.3(2) ne retient pas la borne cot(theta) <= 2,5.
-- Elle la remplace par une expression dependant de l'effort normal et du
-- ferraillage transversal. Le modele scalaire ne peut pas la porter.
--
-- Trois reponses etaient possibles:
--   * stocker 2,5   -> une valeur que l'annexe belge ne retient pas;
--   * stocker 3     -> la borne du plafond, appliquee hors de son contexte;
--   * ne rien stocker et le dire.
--
-- Seule la troisieme est honnete. Cette migration lui donne une place dans
-- le schema: 'not_representable' est refuse dans TOUS les modes, comme
-- 'deprecated', mais pour une raison differente. Un parametre obsolete a une
-- valeur erronee; celui-ci n'a pas de valeur du tout. Aucune signature
-- d'ingenieur ne le debloque: il faut d'abord etendre le module de calcul.
-- =====================================================================

-- Hors transaction volontairement: PostgreSQL refuse d'employer une valeur
-- d'enum dans la transaction qui l'ajoute, et la contrainte ci-dessous
-- l'emploie.
alter type ndp_validation_status add value if not exists 'not_representable';


begin;

comment on type ndp_validation_status is
  'confirmed: releve par un ingenieur nomme, seul statut utilisable en mode '
  'strict. pending_verification: suppose, bloque en mode strict. '
  'deprecated: remplace ou erronee, refuse partout. '
  'not_representable: l''annexe fixe le parametre sous une forme non '
  'scalaire, refuse partout, non debloquable par une signature.';

alter table national_annex_parameters
  alter column parameter_value drop not null;

-- L'absence de valeur et le statut vont ensemble, dans les deux sens. Sans
-- cette contrainte, une valeur perdue lors d'un import ressemblerait a une
-- valeur volontairement absente, et l'inverse.
alter table national_annex_parameters
  add constraint value_absent_iff_not_representable check (
    (parameter_value is null) = (validation_status = 'not_representable')
  );

-- L'INSCRIPTION AU REGISTRE, DANS LA MEME TRANSACTION QUE CE QUI PRECEDE.
-- Les deux variables sont posees par `db/apply_migration.sh`, seul chemin
-- d'application. Sans elles, psql laisse `:'...'` tel quel et la migration
-- echoue sur une erreur de syntaxe: on ne peut donc pas l'appliquer par
-- accident hors du runner.
select normative_migration_applied(:'esc_migration_id', :'esc_migration_sum');

commit;
