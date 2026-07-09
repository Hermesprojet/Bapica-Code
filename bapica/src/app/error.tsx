'use client'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="text-center max-w-md">
        <p className="text-6xl font-bold text-muted-foreground mb-4">500</p>
        <h1 className="text-2xl font-bold mb-2">Une erreur est survenue</h1>
        <p className="text-muted-foreground mb-8">
          {error.message || "Quelque chose s'est mal passé. Réessayez."}
        </p>
        <button
          onClick={reset}
          className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-foreground px-6 text-sm font-medium text-background hover:bg-foreground/90 transition-all"
        >
          Réessayer
        </button>
      </div>
    </div>
  )
}
