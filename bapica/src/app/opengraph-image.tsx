import { ImageResponse } from "next/og"

export const runtime = "edge"
export const alt = "Bapica — Agents IA pour votre entreprise"
export const size = { width: 1200, height: 630 }
export const contentType = "image/png"

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #0a0f1e 0%, #1a1f3e 50%, #0d1225 100%)",
          fontFamily: "Manrope, system-ui, sans-serif",
          padding: "80px",
          position: "relative",
        }}
      >
        {/* Background glow */}
        <div
          style={{
            position: "absolute",
            top: "-20%",
            right: "-10%",
            width: "500px",
            height: "500px",
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(99,102,241,0.15), transparent 70%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: "-30%",
            left: "-5%",
            width: "400px",
            height: "400px",
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(59,130,246,0.1), transparent 70%)",
          }}
        />

        {/* Logo */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
            marginBottom: "40px",
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 13,
              background: "linear-gradient(135deg, #3b82f6, #6366f1, #818cf8)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 24,
              fontWeight: 700,
              color: "#fff",
            }}
          >
            B
          </div>
          <span
            style={{
              fontSize: 36,
              fontWeight: 700,
              color: "#ffffff",
              letterSpacing: "-0.02em",
            }}
          >
            Bapica
          </span>
        </div>

        {/* Main headline */}
        <h1
          style={{
            fontSize: 56,
            fontWeight: 800,
            color: "#ffffff",
            textAlign: "center",
            lineHeight: 1.15,
            maxWidth: "900px",
            marginBottom: "24px",
            letterSpacing: "-0.02em",
          }}
        >
          Votre entreprise mérite{" "}
          <span style={{ background: "linear-gradient(135deg, #6366f1, #818cf8)", backgroundClip: "text", color: "transparent" }}>
            ses propres agents IA
          </span>
        </h1>

        {/* Subtitle */}
        <p
          style={{
            fontSize: 24,
            color: "#94a3b8",
            textAlign: "center",
            maxWidth: "700px",
            lineHeight: 1.5,
          }}
        >
          12 agents spécialisés qui comprennent votre métier et exécutent vos tâches 24h/24
        </p>

        {/* Badge row */}
        <div
          style={{
            display: "flex",
            gap: "16px",
            marginTop: "40px",
          }}
        >
          {["Prospection", "Support", "Contenu", "Voix", "Comptabilité"].map((label) => (
            <span
              key={label}
              style={{
                padding: "6px 18px",
                borderRadius: 20,
                background: "rgba(99,102,241,0.12)",
                color: "#a5b4fc",
                fontSize: 16,
                fontWeight: 500,
              }}
            >
              {label}
            </span>
          ))}
        </div>

        {/* Footer */}
        <div
          style={{
            position: "absolute",
            bottom: 32,
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: 16,
            color: "#64748b",
          }}
        >
          bapica.com · Essai gratuit 14 jours
        </div>
      </div>
    ),
    { ...size }
  )
}
