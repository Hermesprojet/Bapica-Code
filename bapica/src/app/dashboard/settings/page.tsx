'use client'

import { useState } from 'react'
import { Save, Eye, EyeOff, Key } from 'lucide-react'

export default function SettingsPage() {
  const [showApiKey, setShowApiKey] = useState(false)
  const [apiKey, setApiKey] = useState('')
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    // TODO: Sauvegarder dans Supabase
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Paramètres</h1>
        <p className="mt-1 text-muted-foreground">
          Configurez votre plateforme et vos intégrations.
        </p>
      </div>

      <div className="space-y-6">
        {/* API Keys */}
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Key className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h3 className="font-semibold">Clé API Claude / OpenAI</h3>
              <p className="text-sm text-muted-foreground">
                Requise pour faire fonctionner les agents IA
              </p>
            </div>
          </div>
          <div className="flex gap-3">
            <div className="relative flex-1">
              <input
                type={showApiKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-ant-... ou sk-proj-..."
                className="w-full rounded-lg border border-border bg-background px-4 py-2.5 pr-10 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <button
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <button
              onClick={handleSave}
              className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              <Save className="h-4 w-4" />
              {saved ? 'Sauvegardé !' : 'Sauvegarder'}
            </button>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Votre clé est stockée de manière sécurisée et n&apos;est jamais partagée.
          </p>
        </div>

        {/* Profile */}
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 font-semibold">Profil</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1.5">Nom de l&apos;entreprise</label>
              <input
                type="text"
                className="w-full max-w-md rounded-lg border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="Ma PME"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">Email</label>
              <input
                type="email"
                className="w-full max-w-md rounded-lg border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="vous@exemple.fr"
              />
            </div>
          </div>
        </div>

        {/* Langue */}
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 font-semibold">Langue par défaut</h3>
          <select className="w-full max-w-xs rounded-lg border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary">
            <option value="fr">Français</option>
            <option value="en">English</option>
            <option value="ar">العربية</option>
          </select>
        </div>
      </div>
    </div>
  )
}
