import { NextRequest, NextResponse } from "next/server"
import { createClient } from "@supabase/supabase-js"

interface TwentyWebhookPayload {
  eventName: string
  workspaceId: string
  record: Record<string, any>
}

export async function POST(request: NextRequest) {
  const secret = request.headers.get("x-twenty-webhook-secret")
  if (secret !== process.env.TWENTY_WEBHOOK_SECRET) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  let payload: TwentyWebhookPayload
  try {
    payload = await request.json()
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 })
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || ""
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ""
  const supabase = createClient(supabaseUrl, supabaseKey)

  await supabase.from("crm_events").insert({
    event_name: payload.eventName,
    workspace_id: payload.workspaceId,
    payload: payload.record,
    received_at: new Date().toISOString(),
  })

  switch (payload.eventName) {
    case "opportunity.stage.updated":
      if (payload.record.stage === "WON") {
        await notifyAgent("support", { type: "deal_won", opportunity: payload.record })
      }
      break
    case "person.created":
      await notifyAgent("prospector", { type: "new_contact", person: payload.record })
      break
  }

  return NextResponse.json({ received: true })
}

async function notifyAgent(agentId: string, event: Record<string, unknown>) {
  try {
    await fetch(`${process.env.NEXT_PUBLIC_APP_URL}/api/agents/${agentId}/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(event),
    })
  } catch (e) {
    console.error('Twenty webhook notify failed:', e)
  }
}
