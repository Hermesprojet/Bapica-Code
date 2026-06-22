import { NextResponse } from "next/server"

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const { script, avatar_id, language } = body

    // HeyGen video generation
    console.log("Video generation request:", { script, avatar_id, language })

    // TODO: Appeler HeyGen API
    // const response = await fetch("https://api.heygen.com/v1/video.generate", {
    //   method: "POST",
    //   headers: { "Authorization": `Bearer ${process.env.HEYGEN_API_KEY}` },
    //   body: JSON.stringify({ script, avatar_id, language }),
    // })

    return NextResponse.json({
      status: "processing",
      message: "Video generation started. You will receive a webhook when ready.",
    })
  } catch (error) {
    console.error("Video generation error:", error)
    return NextResponse.json({ error: "Internal server error" }, { status: 500 })
  }
}
