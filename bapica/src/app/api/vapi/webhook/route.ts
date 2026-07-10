import { NextResponse } from "next/server"

export async function POST(req: Request) {
  try {
    // Signature check
    const sig = req.headers.get('x-vapi-signature')
    if (process.env.VAPI_WEBHOOK_SECRET && sig !== process.env.VAPI_WEBHOOK_SECRET) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const body = await req.json()
    const { event, call_id, status } = body

    // Vapi webhook handler

    // Sauvegarder dans Supabase
    try {
      const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || ""
      const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ""
      if (supabaseUrl && supabaseKey) {
        const { createClient } = await import("@supabase/supabase-js")
        const supabase = createClient(supabaseUrl, supabaseKey)
        await supabase.from("vapi_events").insert({ event, call_id, status, payload: body, received_at: new Date().toISOString() })
      }
    } catch (e) {
      console.error("Vapi event save failed:", e)
    }
    // await getSupabaseAdmin().from("calls").insert({ call_id, status, transcript: body.transcript })

    return NextResponse.json({ received: true })
  } catch (error) {
    console.error("Vapi webhook error:", error)
    return NextResponse.json({ error: "Internal server error" }, { status: 500 })
  }
}

export async function GET() {
  return NextResponse.json({ message: "Vapi webhook endpoint ready" })
}
