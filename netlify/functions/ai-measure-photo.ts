declare const Netlify: {
  env: {
    get(name: string): string | undefined
  }
}

type GeminiReviewPayload = {
  imageBase64?: string
  mimeType?: string
  fileName?: string
  enhancedForAi?: boolean
  pipeDiameterMm?: number
  cv?: {
    gapMm?: number
    confidence?: number
    measurementSource?: string
    debug?: unknown
  }
}

type GeminiJsonPart = {
  text?: string
}

type GeminiResponse = {
  candidates?: Array<{
    content?: {
      parts?: GeminiJsonPart[]
    }
  }>
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json',
    },
  })
}

function numberOrNull(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? Number(value.toFixed(1)) : null
}

function booleanOrFalse(value: unknown): boolean {
  return value === true
}

function getCvOverlayHints(debug: unknown): unknown {
  return typeof debug === 'object' && debug && 'overlayHints' in debug ? debug.overlayHints : undefined
}

function parseGeminiJson(response: GeminiResponse): Record<string, unknown> {
  const text = response.candidates?.[0]?.content?.parts?.find((part) => typeof part.text === 'string')?.text
  if (!text) {
    throw new Error('Gemini returned no JSON text.')
  }

  try {
    return JSON.parse(text) as Record<string, unknown>
  } catch {
    const jsonStart = text.indexOf('{')
    const jsonEnd = text.lastIndexOf('}')
    if (jsonStart >= 0 && jsonEnd > jsonStart) {
      return JSON.parse(text.slice(jsonStart, jsonEnd + 1)) as Record<string, unknown>
    }
    throw new Error('Gemini returned text that could not be parsed as JSON.')
  }
}

export default async (req: Request) => {
  if (req.method !== 'POST') {
    return jsonResponse({ error: 'Method not allowed' }, 405)
  }

  const apiKey = Netlify.env.get('GEMINI_API_KEY')
  if (!apiKey) {
    return jsonResponse({ error: 'GEMINI_API_KEY is not configured.' }, 500)
  }

  const model = Netlify.env.get('GEMINI_MODEL') ?? 'gemini-2.5-flash'
  const payload = (await req.json()) as GeminiReviewPayload

  if (!payload.imageBase64 || !payload.mimeType) {
    return jsonResponse({ error: 'imageBase64 and mimeType are required.' }, 400)
  }

  const prompt = [
    'You are reviewing a pipe joint inspection photo. It may be a centered pipe-opening image or a close-up linear seam image.',
    'Use the enhanced image and CV debug data to decide whether the measured gap is visually plausible.',
    'Return only JSON with these fields: usable, jointVisible, pipeOpeningVisible, cvPlausible, estimatedGapMm, confidence, reason, retakeMessage, overlayHints.',
    'estimatedGapMm must be a number or null. confidence must be 0 to 1.',
    'Do not claim perfect accuracy. If the joint edge is unclear, return usable=false and a retakeMessage.',
    'If the image has enough visual scale and joint geometry, estimate the gap in millimetres.',
    'Use the known pipe diameter as the scale reference when provided.',
    'If the joint is visible but the millimetre estimate is uncertain, keep usable=true, set jointVisible=true, and provide a best estimatedGapMm with lower confidence.',
    'For close-up seam photos, pipeOpeningVisible may be false while jointVisible and usable are true.',
    'Only set usable=false when the joint/seam/opening genuinely cannot be inspected from the image.',
    `File: ${payload.fileName ?? 'unknown'}`,
    `Known pipe diameter mm: ${payload.pipeDiameterMm ?? 'unknown'}`,
    `Enhanced before AI review: ${payload.enhancedForAi === true ? 'yes' : 'no'}`,
    `CV evidence: ${JSON.stringify(payload.cv ?? {})}`,
  ].join('\n')

  const geminiResponse = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-goog-api-key': apiKey,
    },
    body: JSON.stringify({
      contents: [
        {
          parts: [
            {
              inline_data: {
                mime_type: payload.mimeType,
                data: payload.imageBase64,
              },
            },
            { text: prompt },
          ],
        },
      ],
      generationConfig: {
        temperature: 0.1,
        response_mime_type: 'application/json',
      },
    }),
  })

  if (!geminiResponse.ok) {
    return jsonResponse({ error: `Gemini API returned ${geminiResponse.status}.` }, 502)
  }

  const raw = (await geminiResponse.json()) as GeminiResponse
  const parsed = parseGeminiJson(raw)

  return jsonResponse({
    provider: 'gemini',
    model,
    usable: booleanOrFalse(parsed.usable),
    jointVisible: booleanOrFalse(parsed.jointVisible),
    pipeOpeningVisible: booleanOrFalse(parsed.pipeOpeningVisible),
    cvPlausible: booleanOrFalse(parsed.cvPlausible),
    estimatedGapMm: numberOrNull(parsed.estimatedGapMm),
    confidence: typeof parsed.confidence === 'number' ? Math.max(0, Math.min(1, parsed.confidence)) : 0.4,
    reason: typeof parsed.reason === 'string' ? parsed.reason : 'Gemini reviewed the inspection image.',
    retakeMessage: typeof parsed.retakeMessage === 'string' ? parsed.retakeMessage : undefined,
    overlayHints: typeof parsed.overlayHints === 'object' && parsed.overlayHints ? parsed.overlayHints : getCvOverlayHints(payload.cv?.debug),
    reviewedAt: new Date().toISOString(),
  })
}

export const config = {
  path: '/api/ai/measure-photo',
  method: ['POST'],
}
