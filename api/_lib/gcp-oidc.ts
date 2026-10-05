/**
 * Vercel OIDC -> Google Cloud Workload Identity Federation (WIF) Exchange
 *
 * Implements token exchange to acquire short-lived, Google-signed ID tokens
 * for private Cloud Run invocation without any static service account keys.
 */

import { getVercelOidcToken } from '@vercel/oidc'
import { GATEWAY_CONFIG } from './config'

interface CachedIdToken {
  token: string
  expiresAtMs: number
}

let cachedIdToken: CachedIdToken | null = null

/**
 * Exchange Vercel OIDC token for Google Cloud Run ID token via Workload Identity Federation.
 */
export async function getCloudRunIdToken(): Promise<string | null> {
  const now = Date.now()

  // Return valid cached token if within validity window (with 5-minute safety buffer)
  if (cachedIdToken && cachedIdToken.expiresAtMs > now + 300_000) {
    return cachedIdToken.token
  }

  const isProduction = process.env.NODE_ENV === 'production' || process.env.VERCEL_ENV === 'production'

  let vercelOidcToken: string | null = null
  try {
    vercelOidcToken = await getVercelOidcToken()
  } catch {
    // If not in Vercel request context, check env vars (non-production only)
    if (!isProduction) {
      vercelOidcToken = process.env.VERCEL_OIDC_TOKEN || process.env.TEST_VERCEL_OIDC_TOKEN || null
    }
  }

  if (!vercelOidcToken) {
    if (!isProduction && process.env.DEV_CLOUD_RUN_ID_TOKEN) {
      return process.env.DEV_CLOUD_RUN_ID_TOKEN
    }
    return null
  }

  const stsAudience = `//iam.googleapis.com/projects/${GATEWAY_CONFIG.GCP_PROJECT_NUMBER}/locations/global/workloadIdentityPools/${GATEWAY_CONFIG.GCP_WORKLOAD_IDENTITY_POOL_ID}/providers/${GATEWAY_CONFIG.GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID}`

  try {
    // Step 1: Exchange Vercel OIDC token for Google STS Federated Access Token
    const stsResponse = await fetch('https://sts.googleapis.com/v1/token', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        grant_type: 'urn:ietf:params:oauth:grant-type:token-exchange',
        audience: stsAudience,
        scope: 'https://www.googleapis.com/auth/cloud-platform',
        requested_token_type: 'urn:ietf:params:oauth:token-type:access_token',
        subject_token_type: 'urn:ietf:params:oauth:token-type:id_token',
        subject_token: vercelOidcToken,
      }),
    })

    if (!stsResponse.ok) {
      const errorText = await stsResponse.text().catch(() => '')
      throw new Error(`Google STS token exchange failed (${stsResponse.status}): ${errorText}`)
    }

    const stsData = (await stsResponse.json()) as { access_token: string; expires_in?: number }
    const stsAccessToken = stsData.access_token

    // Step 2: Impersonate Service Account to generate Cloud Run ID Token
    const iamEndpoint = `https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/${encodeURIComponent(
      GATEWAY_CONFIG.GCP_SERVICE_ACCOUNT_EMAIL
    )}:generateIdToken`

    const idTokenResponse = await fetch(iamEndpoint, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${stsAccessToken}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        audience: GATEWAY_CONFIG.CLOUD_RUN_URL,
        includeEmail: true,
      }),
    })

    if (!idTokenResponse.ok) {
      const errorText = await idTokenResponse.text().catch(() => '')
      throw new Error(`Cloud Run ID token generation failed (${idTokenResponse.status}): ${errorText}`)
    }

    const idTokenData = (await idTokenResponse.json()) as { token: string }
    const idToken = idTokenData.token

    // Cache ID token (default GCP ID tokens expire in 1 hour / 3600 seconds)
    const ttlMs = (stsData.expires_in || 3600) * 1000
    cachedIdToken = {
      token: idToken,
      expiresAtMs: now + ttlMs,
    }

    return idToken
  } catch (error) {
    console.error('Workload Identity Federation exchange failure:', error)
    return null
  }
}
