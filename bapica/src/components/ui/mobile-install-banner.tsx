'use client'

import { useState, useEffect } from 'react'

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

export function MobileInstallBanner() {
  const [showBanner, setShowBanner] = useState(false)
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null)
  const [isIOS, setIsIOS] = useState(false)
  const [isStandalone, setIsStandalone] = useState(false)

  useEffect(() => {
    // Détecter si déjà en mode standalone (app installée)
    if (window.matchMedia('(display-mode: standalone)').matches) {
      setIsStandalone(true)
      return
    }

    // Détecter iOS
    const ios = /iphone|ipad|ipod/.test(navigator.userAgent.toLowerCase())
    setIsIOS(ios)

    // Intercepter l'événement beforeinstallprompt (Android/Chrome)
    const handler = (e: Event) => {
      e.preventDefault()
      setDeferredPrompt(e as BeforeInstallPromptEvent)
      setShowBanner(true)
    }
    window.addEventListener('beforeinstallprompt', handler)

    // Pour iOS : montrer après 10s sur le site
    if (ios) {
      setTimeout(() => {
        const dismissed = localStorage.getItem('bapica_install_dismissed')
        if (!dismissed) setShowBanner(true)
      }, 10000)
    }

    return () => window.removeEventListener('beforeinstallprompt', handler)
  }, [])

  const handleInstall = async () => {
    if (deferredPrompt) {
      await deferredPrompt.prompt()
      const { outcome } = await deferredPrompt.userChoice
      if (outcome === 'accepted') {
        setShowBanner(false)
      }
      setDeferredPrompt(null)
    } else if (isIOS) {
      // Montrer les instructions iOS
      alert('📱 Pour installer Bapica sur votre iPhone :\n\n1. Appuyez sur l\'icône "Partager" en bas de l\'écran\n2. Faites défiler et appuyez sur "Sur l\'écran d\'accueil"\n3. Appuyez sur "Ajouter"')
    }
  }

  const handleDismiss = () => {
    setShowBanner(false)
    localStorage.setItem('bapica_install_dismissed', 'true')
  }

  if (!showBanner || isStandalone) return null

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 p-4 bg-white border-t border-[#E5E7EB] shadow-2xl animate-slide-up">
      <div className="container mx-auto max-w-7xl flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-[#2563EB] flex items-center justify-center text-white text-2xl font-bold shrink-0">
            B
          </div>
          <div>
            <div className="font-bold text-[#111827]">Application Bapica</div>
            <div className="text-sm text-[#6B7280]">Plus rapide, notifications, toujours à portée de main</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleDismiss}
            className="text-sm text-[#9CA3AF] hover:text-[#6B7280] px-3 py-2"
          >
            Plus tard
          </button>
          <button
            onClick={handleInstall}
            className="px-5 py-2.5 bg-[#2563EB] text-white rounded-lg font-semibold text-sm hover:bg-[#1D4ED8] transition-colors whitespace-nowrap"
          >
            {isIOS ? 'Installer' : 'Télécharger'}
          </button>
        </div>
      </div>
    </div>
  )
}
