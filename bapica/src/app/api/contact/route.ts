import { NextRequest, NextResponse } from "next/server"

// Rate limiting simple (50 req / 15 min par IP)
const rateLimit = new Map<string, { count: number; reset: number }>()

export async function POST(req: NextRequest) {
  const ip = req.headers.get("x-forwarded-for") || req.headers.get("x-real-ip") || "unknown"
  const now = Date.now()
  const limit = rateLimit.get(ip)
  
  if (limit && now < limit.reset && limit.count >= 50) {
    return NextResponse.json({ error: "Trop de requêtes." }, { status: 429 })
  }
  if (!limit || now >= limit.reset) {
    rateLimit.set(ip, { count: 1, reset: now + 15 * 60 * 1000 })
  } else {
    limit.count++
  }
  
  try {
    const { name, email, message } = await req.json()

    if (!name || !email || !message) {
      return NextResponse.json(
        { error: "Tous les champs sont requis." },
        { status: 400 }
      )
    }

    if (typeof name !== "string" || name.length > 100) {
      return NextResponse.json(
        { error: "Nom invalide." },
        { status: 400 }
      )
    }

    if (typeof email !== "string" || !email.includes("@") || email.length > 150) {
      return NextResponse.json(
        { error: "Email invalide." },
        { status: 400 }
      )
    }

    if (typeof message !== "string" || message.length > 2000) {
      return NextResponse.json(
        { error: "Message trop long (max 2000 caractères)." },
        { status: 400 }
      )
    }

    // TODO: Send email notification (Resend/SendGrid) or store in Supabase
    if (process.env.NODE_ENV === "development") {
      console.log(`[Contact] ${name} <${email}>: ${message.slice(0, 100)}...`)
    }

    return NextResponse.json({ success: true })
  } catch {
    return NextResponse.json(
      { error: "Requête invalide." },
      { status: 400 }
    )
  }
}
