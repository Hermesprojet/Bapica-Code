import { LeadFinderPanel } from '@/components/agents/lead-finder-panel'

export default function ProspectsPage() {
  return (
    <div>
      <div className="reveal mb-6">
        <h1 className="text-2xl font-bold">Trouver des prospects</h1>
        <p className="mt-1 text-muted-foreground">
          Recherchez des contacts B2B : Apollo (découverte par poste, lieu, secteur, taille) ou
          Hunter (personnes et emails d&apos;un domaine d&apos;entreprise). Marc et Nadia s&apos;appuient
          sur les mêmes sources.
        </p>
      </div>
      <LeadFinderPanel persona="Marc" defaultOpen />
    </div>
  )
}
