-- Migration: Ajout des colonnes pour l'onboarding
-- Exécute ce script dans le SQL Editor de Supabase
-- https://supabase.com/dashboard/project/xlivseiybtkwkekyhqwg/sql/new

ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS onboarding_completed boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS onboarding_data jsonb DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS recommended_plan text,
ADD COLUMN IF NOT EXISTS company_activity text;
