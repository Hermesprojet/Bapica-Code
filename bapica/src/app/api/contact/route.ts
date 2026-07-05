import { NextRequest, NextResponse } from "next/server"

export async function POST(req: NextRequest) {
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
