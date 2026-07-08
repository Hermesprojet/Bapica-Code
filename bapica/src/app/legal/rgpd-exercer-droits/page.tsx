import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Protection des données (RGPD)",
  description: "Exercer vos droits RGPD : accès, rectification, effacement et portabilité de vos données personnelles chez Bapica.",
}

export default function GDPRPage() {
  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto max-w-3xl px-4 pt-24 pb-16">
        <h1 className="text-3xl font-bold mb-8">Protection des données (RGPD)</h1>

        <section className="space-y-8">
          <div className="card-professional">
            <h2 className="text-xl font-bold mb-4">🔍 Droit d&apos;accès</h2>
            <p className="text-muted-foreground mb-4">
              Vous pouvez demander une copie de toutes vos données personnelles.
            </p>
            <p className="text-sm text-muted-foreground/60">
              Connectez-vous à votre compte, puis contactez <strong>dpo@bapica.com</strong> ou utilisez l&apos;API <code>GET /api/gdpr/export</code>.
            </p>
          </div>

          <div className="card-professional">
            <h2 className="text-xl font-bold mb-4">🗑️ Droit à l&apos;effacement</h2>
            <p className="text-muted-foreground mb-4">
              Vous pouvez demander la suppression définitive de toutes vos données.
            </p>
            <p className="text-sm text-muted-foreground/60">
              Envoyez <code>POST /api/gdpr/delete</code> avec <code>{"{\"confirmation\": \"SUPPRIMER\"}"}</code> après authentification, ou contactez <strong>dpo@bapica.com</strong>.
            </p>
          </div>

          <div className="card-professional">
            <h2 className="text-xl font-bold mb-4">📧 Contact DPO</h2>
            <p className="text-muted-foreground">
              Pour toute question relative à vos données personnelles :<br />
              <strong>dpo@bapica.com</strong>
            </p>
          </div>
        </section>
      </div>
    </div>
  )
}
