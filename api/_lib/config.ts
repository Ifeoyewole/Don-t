/**
 * Production Security Hardening Configuration Identifiers
 *
 * NOTE: These are public cloud identifiers, NOT permanent private secrets.
 * Permanent private keys or service account credentials must NEVER be placed here.
 */

export const GATEWAY_CONFIG = {
  GCP_PROJECT_ID: process.env.GCP_PROJECT_ID || 'joint-inspection-510310',
  GCP_PROJECT_NUMBER: process.env.GCP_PROJECT_NUMBER || '567370443508',
  GCP_SERVICE_ACCOUNT_EMAIL:
    process.env.GCP_SERVICE_ACCOUNT_EMAIL ||
    'joint-inspect-vercel-invoker@joint-inspection-510310.iam.gserviceaccount.com',
  GCP_WORKLOAD_IDENTITY_POOL_ID: process.env.GCP_WORKLOAD_IDENTITY_POOL_ID || 'vercel',
  GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID:
    process.env.GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID || 'vercel-production',
  CLOUD_RUN_URL: (process.env.CLOUD_RUN_URL || 'https://pipe-joint-api-7d5y5wcyta-nw.a.run.app').replace(/\/$/, ''),

  // Authentication abstraction mode ('disabled' until provider selection is approved)
  USER_AUTH_MODE: (process.env.USER_AUTH_MODE || 'disabled') as 'disabled' | 'provider',

  // Rate Limiting (Requests / minute / IP)
  RATE_LIMITS: {
    HEALTH: parseInt(process.env.RATE_LIMIT_HEALTH || '60', 10),
    VALIDATION: parseInt(process.env.RATE_LIMIT_VALIDATION || '30', 10),
    MEASURE: parseInt(process.env.RATE_LIMIT_MEASURE || '20', 10),
    MULTI_FRAME: parseInt(process.env.RATE_LIMIT_MULTI_FRAME || '5', 10),
    CALIBRATION_READ: parseInt(process.env.RATE_LIMIT_CALIBRATION_READ || '30', 10),
    CALIBRATION_MUTATE: parseInt(process.env.RATE_LIMIT_CALIBRATION_MUTATE || '5', 10),
  },

  // Payload constraints
  MAX_UPLOAD_SIZE_BYTES: 15 * 1024 * 1024, // 15 MB
  MAX_MULTI_FRAME_BYTES: 30 * 1024 * 1024, // 30 MB
  MAX_MULTI_FRAME_COUNT: 30,

  // Allowed image MIME types
  ALLOWED_IMAGE_MIMES: ['image/jpeg', 'image/png', 'image/webp'],
} as const

// Production environment validation: forbid development / test token fallbacks
const isProduction = process.env.NODE_ENV === 'production' || process.env.VERCEL_ENV === 'production'
if (isProduction) {
  if (process.env.DEV_CLOUD_RUN_ID_TOKEN || process.env.TEST_VERCEL_OIDC_TOKEN) {
    throw new Error('FATAL SECURITY: DEV_CLOUD_RUN_ID_TOKEN and TEST_VERCEL_OIDC_TOKEN are strictly forbidden in production.')
  }
}

export const ALLOWED_ORIGINS = [
  'https://joint-inspection.vercel.app',
  ...(process.env.NODE_ENV !== 'production' ? ['http://localhost:5173', 'http://127.0.0.1:5173'] : []),
] as const
