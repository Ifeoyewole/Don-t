/**
 * Dedicated Vercel Serverless Gateway Handler for Health Check
 */

import type { IncomingMessage, ServerResponse } from 'http'
import handler from './[...route]'

export default function healthHandler(req: IncomingMessage, res: ServerResponse) {
  return handler(req, res)
}
