-- Bapica - Schema de base de donnees
-- Execute ce script dans Supabase SQL Editor

-- 1. Profiles utilisateurs
CREATE TABLE IF NOT EXISTS profiles (
  id UUID REFERENCES auth.users PRIMARY KEY,
  email TEXT,
  company_name TEXT,
  full_name TEXT,
  avatar_url TEXT,
  plan TEXT DEFAULT 'starter',
  stripe_customer_id TEXT,
  stripe_subscription_id TEXT,
  api_used INTEGER DEFAULT 0,
  api_limit INTEGER DEFAULT 100,
  language TEXT DEFAULT 'fr',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Conversations
CREATE TABLE IF NOT EXISTS conversations (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) NOT NULL,
  agent_id TEXT NOT NULL,
  title TEXT DEFAULT 'Nouvelle conversation',
  messages JSONB DEFAULT '[]',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Abonnements
CREATE TABLE IF NOT EXISTS subscriptions (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) NOT NULL,
  plan TEXT NOT NULL DEFAULT 'starter',
  status TEXT NOT NULL DEFAULT 'active',
  stripe_price_id TEXT,
  current_period_start TIMESTAMPTZ,
  current_period_end TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. API Keys utilisateur
CREATE TABLE IF NOT EXISTS api_keys (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) NOT NULL,
  name TEXT NOT NULL,
  key_value TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  last_used_at TIMESTAMPTZ
);

-- 5. Logs d'utilisation
CREATE TABLE IF NOT EXISTS usage_logs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) NOT NULL,
  agent_id TEXT NOT NULL,
  tokens_used INTEGER DEFAULT 0,
  api_calls INTEGER DEFAULT 1,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Connexions réseaux sociaux (jetons OAuth par plateforme)
CREATE TABLE IF NOT EXISTS social_connections (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) NOT NULL,
  platform TEXT NOT NULL,          -- 'linkedin', 'facebook', 'instagram', ...
  access_token TEXT NOT NULL,
  refresh_token TEXT,
  expires_at TIMESTAMPTZ,
  external_id TEXT,                -- id du compte sur la plateforme (ex: sub LinkedIn)
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, platform)
);

-- 7. Connexions de messagerie par client (hub multi-client : Telegram, WhatsApp…)
--    credentials JSONB : telegram { botToken } ; whatsapp { ... }.
--    webhook_secret : secret unique renvoyé par la plateforme pour identifier le client.
CREATE TABLE IF NOT EXISTS channel_connections (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) NOT NULL,
  platform TEXT NOT NULL,                     -- 'telegram' | 'whatsapp'
  credentials JSONB NOT NULL DEFAULT '{}',
  external_id TEXT,                            -- telegram: bot username ; whatsapp: numéro E.164
  webhook_secret TEXT,                        -- telegram secret_token / clé de routage
  status TEXT DEFAULT 'connected',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, platform)
);

-- 8. Actions proposées par les agents, en attente de validation humaine.
--    L'agent ne peut QUE proposer ; seul le serveur exécute après approbation.
CREATE TABLE IF NOT EXISTS pending_actions (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) NOT NULL,
  agent_id TEXT,
  provider TEXT NOT NULL,                      -- plateforme cible (stripe, pennylane, custom:...)
  method TEXT NOT NULL,                        -- POST | PUT | PATCH | DELETE
  path TEXT NOT NULL,                          -- chemin relatif de l'API
  body JSONB,                                  -- corps de la requête
  summary TEXT NOT NULL,                       -- résumé lisible présenté à l'utilisateur
  status TEXT NOT NULL DEFAULT 'pending',      -- pending | executed | rejected | failed
  result TEXT,                                 -- retour de la plateforme après exécution
  created_at TIMESTAMPTZ DEFAULT NOW(),
  decided_at TIMESTAMPTZ
);

-- 9. Signaux d'expérience client (apprentissage produit) : questions au chatbot d'aide,
--    feedback explicite, frictions/échecs. Agrégés en rapport pour l'administrateur.
CREATE TABLE IF NOT EXISTS client_signals (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID,
  type TEXT NOT NULL,             -- 'question' | 'feedback' | 'action_failed' | ...
  content TEXT NOT NULL,
  meta JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_pending_actions_user ON pending_actions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_client_signals_created ON client_signals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_channel_conn_user ON channel_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_channel_conn_secret ON channel_connections(webhook_secret);
CREATE INDEX IF NOT EXISTS idx_channel_conn_external ON channel_connections(platform, external_id);
CREATE INDEX IF NOT EXISTS idx_social_connections_user ON social_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_user ON usage_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_date ON usage_logs(created_at);

-- Enable Row Level Security
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_logs ENABLE ROW LEVEL SECURITY;
-- Jetons sociaux : RLS activée sans policy (accès uniquement via service_role serveur).
ALTER TABLE social_connections ENABLE ROW LEVEL SECURITY;
-- Connexions de messagerie : RLS activée sans policy (accès service_role uniquement).
ALTER TABLE channel_connections ENABLE ROW LEVEL SECURITY;
-- Actions en attente : RLS activée sans policy (accès service_role uniquement).
ALTER TABLE pending_actions ENABLE ROW LEVEL SECURITY;
-- Signaux clients : RLS activée sans policy (accès service_role / admin uniquement).
ALTER TABLE client_signals ENABLE ROW LEVEL SECURITY;

-- Policies
-- NB : CREATE POLICY n'a pas de « IF NOT EXISTS ». Chaque policy est donc précédée d'un
-- DROP POLICY IF EXISTS pour que ce fichier reste REJOUABLE (aucune erreur si on le relance).
DROP POLICY IF EXISTS "Users can view own profile" ON profiles;
CREATE POLICY "Users can view own profile" ON profiles
  FOR SELECT USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can update own profile" ON profiles;
CREATE POLICY "Users can update own profile" ON profiles
  FOR UPDATE USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can view own conversations" ON conversations;
CREATE POLICY "Users can view own conversations" ON conversations
  FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own conversations" ON conversations;
CREATE POLICY "Users can insert own conversations" ON conversations
  FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own conversations" ON conversations;
CREATE POLICY "Users can update own conversations" ON conversations
  FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own conversations" ON conversations;
CREATE POLICY "Users can delete own conversations" ON conversations
  FOR DELETE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view own subscriptions" ON subscriptions;
CREATE POLICY "Users can view own subscriptions" ON subscriptions
  FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view own API keys" ON api_keys;
CREATE POLICY "Users can view own API keys" ON api_keys
  FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own API keys" ON api_keys;
CREATE POLICY "Users can insert own API keys" ON api_keys
  FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own API keys" ON api_keys;
CREATE POLICY "Users can delete own API keys" ON api_keys
  FOR DELETE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view own usage logs" ON usage_logs;
CREATE POLICY "Users can view own usage logs" ON usage_logs
  FOR SELECT USING (auth.uid() = user_id);

-- Fonction pour créer un profil automatiquement à l'inscription
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, email, company_name, full_name)
  VALUES (
    NEW.id,
    NEW.email,
    NEW.raw_user_meta_data->>'company_name',
    NEW.raw_user_meta_data->>'full_name'
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger pour création automatique de profil
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ─────────────────────────────────────────────────────────────
-- RAG par client : documents téléversés → base de connaissances
-- propre à l'entreprise du client (embeddings OpenAI 1536 dims).
-- Nécessite l'extension pgvector.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS client_knowledge (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) NOT NULL,
  source TEXT NOT NULL,           -- nom du document
  content TEXT NOT NULL,          -- extrait (chunk)
  embedding VECTOR(1536),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_client_knowledge_user ON client_knowledge(user_id);
CREATE INDEX IF NOT EXISTS idx_client_knowledge_embedding
  ON client_knowledge USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Jetons/documents sensibles : RLS activée sans policy (accès service_role only).
ALTER TABLE client_knowledge ENABLE ROW LEVEL SECURITY;

-- Recherche sémantique scopée par utilisateur.
CREATE OR REPLACE FUNCTION match_client_knowledge(
  query_embedding VECTOR(1536),
  filter_user_id UUID,
  match_threshold FLOAT,
  match_count INT
)
RETURNS TABLE (id UUID, source TEXT, content TEXT, similarity FLOAT)
LANGUAGE sql STABLE AS $$
  SELECT id, source, content, 1 - (embedding <=> query_embedding) AS similarity
  FROM client_knowledge
  WHERE user_id = filter_user_id
    AND 1 - (embedding <=> query_embedding) > match_threshold
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;

-- ─────────────────────────────────────────────────────────────
-- 10. Documents produits par les agents (devis, rapports, tableaux) — téléchargeables.
--     Généré à la demande (pas d'action externe) : accès service_role uniquement.
CREATE TABLE IF NOT EXISTS deliverables (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) NOT NULL,
  agent_id TEXT,
  kind TEXT NOT NULL,            -- pdf | excel | csv | markdown | text
  title TEXT NOT NULL,
  filename TEXT NOT NULL,
  mime TEXT NOT NULL,
  content TEXT NOT NULL,         -- corps du fichier (HTML pour pdf, CSV, markdown…)
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_deliverables_user ON deliverables(user_id, created_at DESC);
ALTER TABLE deliverables ENABLE ROW LEVEL SECURITY;

-- 11. Étiquettes d'échanges (appels, messages) : prospect intéressé, SAV, impayé…
CREATE TABLE IF NOT EXISTS interaction_tags (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) NOT NULL,
  agent_id TEXT,
  channel TEXT,                  -- chat | whatsapp | telephone | email…
  contact TEXT,                  -- nom/numéro/email de l'interlocuteur (optionnel)
  tag TEXT NOT NULL,             -- prospect_interesse | rappel_demande | sav | impaye | pas_interesse | autre
  note TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_interaction_tags_user ON interaction_tags(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_interaction_tags_tag ON interaction_tags(user_id, tag);
ALTER TABLE interaction_tags ENABLE ROW LEVEL SECURITY;

-- 12. Relances d'impayés programmées (échéancier J+7/J+15/J+30) par Claire.
CREATE TABLE IF NOT EXISTS payment_reminders (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) NOT NULL,
  client TEXT NOT NULL,          -- client débiteur
  contact_email TEXT,            -- destinataire des relances
  invoice_ref TEXT,              -- référence facture
  amount NUMERIC,                -- montant dû
  currency TEXT DEFAULT 'EUR',
  stage TEXT NOT NULL DEFAULT 'amiable',    -- amiable | ferme | mise_en_demeure
  due_on DATE NOT NULL,          -- date d'envoi prévue
  subject TEXT,
  body TEXT,                     -- corps de la relance (rédigé par Claire)
  status TEXT NOT NULL DEFAULT 'scheduled', -- scheduled | sent | cancelled | paid
  created_at TIMESTAMPTZ DEFAULT NOW(),
  sent_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_payment_reminders_user ON payment_reminders(user_id, due_on);
ALTER TABLE payment_reminders ENABLE ROW LEVEL SECURITY;

-- 13. Automatisations récurrentes (le RÉPÉTABLE délégué à N8N, validé par le client).
--     L'agent PROPOSE l'automatisation ; elle ne tourne qu'après validation (status active).
CREATE TABLE IF NOT EXISTS automations (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) NOT NULL,
  agent_id TEXT,                              -- agent responsable de l'exécution
  title TEXT NOT NULL,
  description TEXT NOT NULL,                  -- consigne exécutée à chaque déclenchement
  cron TEXT NOT NULL,                         -- planification (cron 5 champs, UTC)
  schedule_label TEXT,                        -- planification lisible (ex : « chaque lundi 8h »)
  status TEXT NOT NULL DEFAULT 'pending',     -- pending | active | paused
  n8n_workflow_id TEXT,                       -- id du workflow N8N créé à la validation
  run_secret TEXT NOT NULL,                   -- authentifie l'appel N8N → /api/automations/run
  last_run_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_automations_user ON automations(user_id, created_at DESC);
ALTER TABLE automations ENABLE ROW LEVEL SECURITY;

-- 14. Stockage des vidéos importées par le client (bucket public « media »).
--     Upload DIRECT navigateur → Supabase Storage (contourne la limite ~4,5 Mo des routes
--     Vercel). L'URL publique alimente ensuite Maya (découper / sous-titrer / traduire),
--     car Shotstack/HeyGen doivent pouvoir télécharger la vidéo. Chemin : uploads/<user_id>/<fichier>.
INSERT INTO storage.buckets (id, name, public)
VALUES ('media', 'media', true)
ON CONFLICT (id) DO UPDATE SET public = true;

-- Lecture publique (nécessaire pour que Shotstack/HeyGen récupèrent le fichier).
DROP POLICY IF EXISTS "media public read" ON storage.objects;
CREATE POLICY "media public read" ON storage.objects
  FOR SELECT USING (bucket_id = 'media');

-- Dépôt réservé à l'utilisateur connecté, dans SON dossier (uploads/<uid>/...).
DROP POLICY IF EXISTS "media user upload" ON storage.objects;
CREATE POLICY "media user upload" ON storage.objects
  FOR INSERT TO authenticated
  WITH CHECK (bucket_id = 'media' AND (storage.foldername(name))[1] = 'uploads' AND (storage.foldername(name))[2] = auth.uid()::text);

-- Suppression de ses propres fichiers.
DROP POLICY IF EXISTS "media user delete" ON storage.objects;
CREATE POLICY "media user delete" ON storage.objects
  FOR DELETE TO authenticated
  USING (bucket_id = 'media' AND (storage.foldername(name))[1] = 'uploads' AND (storage.foldername(name))[2] = auth.uid()::text);
