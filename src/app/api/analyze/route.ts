import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData()
    const file = formData.get('xray') as File | null

    if (!file) {
      return NextResponse.json({ error: 'No file provided' }, { status: 400 })
    }

    // TODO: In production, forward to GPU inference endpoint
    // const inferenceUrl = process.env.INFERENCE_API_URL
    // const inferenceRes = await fetch(inferenceUrl + '/predict', { method: 'POST', body: formData })

    const mockResult = {
      image_url: '/api/images/original',
      annotated_url: '',
      inference_time_ms: 74,
      detections: [
        { class: 'Deep Caries', confidence: 0.334, bbox: [742, 244, 825, 372] },
        { class: 'Impacted', confidence: 0.85, bbox: [180, 120, 320, 280] },
        { class: 'Caries', confidence: 0.48, bbox: [580, 180, 680, 290] },
        { class: 'Periapical Lesion', confidence: 0.29, bbox: [420, 350, 490, 420] }
      ]
    }

    return NextResponse.json(mockResult)
  } catch (error) {
    console.error('Analysis error:', error)
    return NextResponse.json({ error: 'Analysis failed' }, { status: 500 })
  }
}