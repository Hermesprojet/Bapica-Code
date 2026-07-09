export default function Loading() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-foreground border-t-transparent" />
        <p className="text-muted-foreground">Chargement...</p>
      </div>
    </div>
  )
}
