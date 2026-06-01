import type { IncomingMessage, ServerResponse } from 'node:http'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

type AiMeasurePayload = {
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

type GeminiResponse = {
  candidates?: Array<{
    content?: {
      parts?: Array<{ text?: string }>
    }
  }>
}

function sendJson(response: ServerResponse, status: number, body: unknown): void {
  response.statusCode = status
  response.setHeader('Content-Type', 'application/json')
  response.end(JSON.stringify(body))
}

function readJsonBody(request: IncomingMessage): Promise<AiMeasurePayload> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = []
    request.on('data', (chunk: Buffer) => chunks.push(chunk))
    request.on('end', () => {
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString('utf8')) as AiMeasurePayload)
      } catch {
        reject(new Error('Invalid JSON request body.'))
      }
    })
    request.on('error', reject)
  })
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

function numberOrNull(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? Number(value.toFixed(1)) : null
}

function getCvOverlayHints(debug: unknown): unknown {
  return typeof debug === 'object' && debug && 'overlayHints' in debug ? debug.overlayHints : undefined
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [
      react(),
      {
        name: 'local-gemini-api',
        configureServer(server) {
          server.middlewares.use('/api/ai/measure-photo', async (request, response) => {
            if (request.method !== 'POST') {
              sendJson(response, 405, { error: 'Method not allowed' })
              return
            }

            const apiKey = env.GEMINI_API_KEY
            if (!apiKey) {
              sendJson(response, 500, { error: 'GEMINI_API_KEY is not configured.' })
              return
            }

            try {
              const payload = await readJsonBody(request)
              if (!payload.imageBase64 || !payload.mimeType) {
                sendJson(response, 400, { error: 'imageBase64 and mimeType are required.' })
                return
              }

              const model = env.GEMINI_MODEL || 'gemini-2.5-flash'
              const prompt = [
                'You are reviewing a pipe joint inspection photo. It may be a centered pipe-opening image or a close-up linear seam image.',
                'Use the enhanced image to independently estimate the joint gap. Use CV debug data only as supporting evidence for where the joint is, not as the final answer.',
                'Important: in close-up photos, the dark or black slot between the two pipe/concrete edges is the joint gap to inspect. Treat that black void as the measurable gap, not as a missing/invalid image area.',
                'If two solid edges are visible on either side of a black slot, set jointVisible=true and usable=true even when the pipe opening is not visible.',
                'Trace the centerline or edge path of that black gap in overlayHints.jointTrace. When possible, also return overlayHints.jointEdgeA and overlayHints.jointEdgeB as the two visible sides of the black slot.',
                'Return only JSON with these fields: usable, jointVisible, pipeOpeningVisible, cvPlausible, estimatedGapMm, confidence, reason, retakeMessage, overlayHints.',
                'estimatedGapMm must be a number or null. confidence must be 0 to 1.',
                'overlayHints may include pipeCenter, innerRadiusPx, outerRadiusPx, gapLine, and jointTrace.',
                'When marking a visible seam/joint, prefer overlayHints.jointTrace as 8 to 40 image-coordinate points that follow the actual curved or angled joint edge. Do not replace a curved joint with a straight line.',
                'If a visible scale reference exists in the image, return estimatedGapMm as a measurement estimate from that scale.',
                'If no visible scale reference exists but the black gap is clear, still return a rough visual estimatedGapMm and lower confidence. Explain that it is uncalibrated and not a confirmed measurement.',
                'A known pipe diameter helps only when the pipe opening or another known-size reference is visible in that same image.',
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
                sendJson(response, 502, { error: `Gemini API returned ${geminiResponse.status}.` })
                return
              }

              const parsed = parseGeminiJson((await geminiResponse.json()) as GeminiResponse)
              sendJson(response, 200, {
                provider: 'gemini',
                model,
                usable: parsed.usable === true,
                jointVisible: parsed.jointVisible === true,
                pipeOpeningVisible: parsed.pipeOpeningVisible === true,
                cvPlausible: parsed.cvPlausible === true,
                estimatedGapMm: numberOrNull(parsed.estimatedGapMm),
                confidence: typeof parsed.confidence === 'number' ? Math.max(0, Math.min(1, parsed.confidence)) : 0.4,
                reason: typeof parsed.reason === 'string' ? parsed.reason : 'Gemini reviewed the inspection image.',
                retakeMessage: typeof parsed.retakeMessage === 'string' ? parsed.retakeMessage : undefined,
                overlayHints: typeof parsed.overlayHints === 'object' && parsed.overlayHints ? parsed.overlayHints : getCvOverlayHints(payload.cv?.debug),
                reviewedAt: new Date().toISOString(),
              })
            } catch (error) {
              console.error(error)
              sendJson(response, 500, { error: error instanceof Error ? error.message : 'Gemini review failed.' })
            }
          })
        },
      },
    ],
  }
})
