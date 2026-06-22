#!/usr/bin/env bash
# ============================================================
# Hermes SaaS Dev Agent — Commande rapide
# Usage: source saas-dev.sh
# Puis : saas "génère la landing page"
# ============================================================

saas() {
  local prompt="$*"
  if [ -z "$prompt" ]; then
    echo "Usage: saas \"ta demande de développement\""
    echo ""
    echo "Exemples :"
    echo "  saas \"génère la landing page complète\""
    echo "  saas \"crée le composant de chat pour l'agent prospecteur\""
    echo "  saas \"configure Stripe webhook\""
    return 1
  fi

  echo "🚀 Lancement de l'agent SaaS Dev..."
  echo "📋 Tâche : $prompt"
  echo ""
  echo "📁 Projet : /workspace/hermes-saas/"
  echo ""
  echo "Pour que Hermes prenne cette tâche, charge la skill :"
  echo "  skill_view('multi-agent-saas')"
  echo "  skill_view('saas-dev-agent')"
  echo ""
  echo "Puis exécute dans le chat Hermes :"
  echo "  $prompt"
}
