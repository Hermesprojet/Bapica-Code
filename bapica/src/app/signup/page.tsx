'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import Link from 'next/link'
import { Loader2, Mail, CheckCircle, ArrowRight } from 'lucide-react'

export default function SignupPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [company, setCompany] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [resending, setResending] = useState(false)
  const router = useRouter()

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    const { data, error: authError } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          company_name: company || 'Mon entreprise',
        },
      },
    })

    if (authError) {
      setError(authError.message === 'User already registered'
        ? 'Un compte existe déjà avec cet email.'
        : authError.message
      )
      setLoading(false)
      return
    }

    // Vérifier si l'email nécessite confirmation
    if (data?.user?.identities?.length === 0) {
      setError('Un compte existe déjà avec cet email.')
      setLoading(false)
      return
    }

    // Si l'utilisateur est déjà confirmé (confirmation désactivée dans Supabase)
    if (data?.user?.email_confirmed_at) {
      router.push('/onboarding')
      return
    }

    // Email de confirmation envoyé
    setSuccess(true)
    setLoading(false)
  }

  const handleResend = async () => {
    setResending(true)
    const { error: resendError } = await supabase.auth.resend({
      type: 'signup',
      email,
    })
    if (resendError) {
      setError(resendError.message)
    }
    setResending(false)
  }

  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="w-full max-w-md text-center">
          <div className="inline-flex items-center justify-center h-16 w-16 rounded-full bg-primary/10 mb-6">
            <Mail className="h-8 w-8 text-primary" />
          </div>
          <h1 className="text-2xl font-bold">Vérifiez votre email</h1>
          <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
            Un email de confirmation a été envoyé à <strong>{email}</strong>.
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            Cliquez sur le lien dans l&apos;email pour activer votre compte, puis connectez-vous.
          </p>

          <div className="mt-8 rounded-xl border border-border bg-card p-4">
            <p className="text-xs text-muted-foreground">
              Vous n&apos;avez pas reçu l&apos;email ? Vérifiez vos spams ou{' '}
              <button
                onClick={handleResend}
                disabled={resending}
                className="text-primary hover:underline disabled:opacity-50"
              >
                {resending ? 'Envoi...' : 'renvoyez-le'}
              </button>
            </p>
          </div>

          <Link
            href="/login"
            className="mt-6 inline-flex items-center gap-2 text-sm text-primary hover:underline"
          >
            Aller à la connexion
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <Link href="/" className="text-2xl font-bold">
            <span className="gradient-text">Bapica</span>
          </Link>
          <h1 className="mt-6 text-2xl font-bold">Créer un compte</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Commencez gratuitement. Sans engagement.
          </p>
        </div>

        <form onSubmit={handleSignup} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1.5">Entreprise</label>
            <input
              type="text"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="Ma PME"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1.5">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="vous@exemple.fr"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1.5">Mot de passe</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="•••••••• (min. 6 caractères)"
              required
              minLength={6}
            />
          </div>

          {error && (
            <div className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-primary to-blue-500 px-4 py-2.5 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50 transition-all shadow-lg shadow-primary/25"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : (
              <>
                Créer mon compte
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          Déjà inscrit ?{' '}
          <Link href="/login" className="text-primary hover:underline font-medium">
            Se connecter
          </Link>
        </p>

        <p className="mt-4 text-center text-xs text-muted-foreground">
          En créant un compte, vous acceptez nos{' '}
          <Link href="/legal/cgv" className="hover:underline">CGV</Link>
        </p>
      </div>
    </div>
  )
}
