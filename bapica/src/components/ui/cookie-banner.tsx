'use client'

import { useState, useEffect } from 'react'

export function CookieBanner() {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const consent = localStorage.getItem('cookie-consent')
    if (!consent) {
      setVisible(true)
    }
  }, [])

  const handleAccept = () => {
    localStorage.setItem('cookie-consent', 'accepted')
    // Dispatch event for PostHog/GTM consent
    window.dispatchEvent(new CustomEvent('cookie:consent', { detail: { marketing: true } }))
    setVisible(false)
  }

  const handleDecline = () => {
    localStorage.setItem('cookie-consent', 'declined')
    window.dispatchEvent(new CustomEvent('cookie:consent', { detail: { marketing: false } }))
    setVisible(false)
  }

  if (!visible) return null

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-card/95 backdrop-blur-md p-4 animate-slide-up">
      <div className="container mx-auto flex flex-wrap items-center justify-between gap-4 px-4">
        <p className="text-sm text-muted-foreground max-w-2xl">
          Nous utilisons des cookies pour améliorer votre expérience. En continuant, vous acceptez notre{' '}
          <a href="/legal/privacy" className="text-primary hover:underline">politique de confidentialité</a>.
        </p>
        <div className="flex items-center gap-3">
          <button
            onClick={handleDecline}
            className="rounded-lg border border-border px-4 py-2 text-sm hover:bg-muted transition-colors"
          >
            Refuser
          </button>
          <button
            onClick={handleAccept}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            Accepter
          </button>
        </div>
      </div>
    </div>
  )
}
