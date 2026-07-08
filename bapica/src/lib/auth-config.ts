/**
 * Configuration de sécurité Supabase Auth
 * Appliqué dans le middleware et le layout
 */

// Ces réglages sont appliqués côté Supabase (dashboard Auth settings)
// et côté client lors de la création du client Supabase.

export const AUTH_COOKIE_OPTIONS = {
  // SameSite: Strict empêche les attaques CSRF
  // mais peut casser les redirections OAuth/stripe
  sameSite: 'lax' as const,
  // Secure: true en production uniquement (HTTPS)
  secure: process.env.NODE_ENV === 'production',
  // HttpOnly: les cookies ne sont pas accessibles en JS
  httpOnly: true,
  // Durée de session : 7 jours
  maxAge: 60 * 60 * 24 * 7,
}

export { sanitize, escapeHtml, isValidEmail, sanitizeUserMessage, isValidAgentId } from './security'
