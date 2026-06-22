import { NextResponse } from "next/server"

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const { event, call_id, status, transcript } = body

    // Vapi webhook handler
    console.log(`Vapi event: ${event}`, { call_id, status })

    // TODO: Sauvegarder dans Supabase
    // const { supabase } = await import("@/lib/supabase")
    // await supabase.from("calls").insert({ call_id, status, transcript })

    return NextResponse.json({ received: true })
  } catch (error) {
    console.error("Vapi webhook error:", error)
    return NextResponse.json({ error: "Internal server error" }, { status: 500 })
  }
}

export async function GET() {
  return NextResponse.json({ message: "Vapi webhook endpoint ready" })
}
