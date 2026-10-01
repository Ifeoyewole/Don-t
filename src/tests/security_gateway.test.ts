import { describe, it, expect } from 'vitest'
import { isMaliciousPath, sanitizeForwardHeaders, validateMagicBytes } from '../../api/_lib/gateway-guard'
import { checkRateLimit } from '../../api/_lib/rate-limiter'
import { DisabledUserAuthProvider, PluggableUserAuthProvider } from '../../api/_lib/auth-abstraction'

describe('Vercel Secure API Gateway Security Controls', () => {
  it('blocks known scanner and malicious paths', () => {
    expect(isMaliciousPath('/wp-admin/login.php')).toBe(true)
    expect(isMaliciousPath('/.env')).toBe(true)
    expect(isMaliciousPath('/.git/config')).toBe(true)
    expect(isMaliciousPath('/phpmyadmin/index.php')).toBe(true)
    expect(isMaliciousPath('/server-status')).toBe(true)
    expect(isMaliciousPath('/api/v1/cv/health')).toBe(false)
    expect(isMaliciousPath('/api/v1/cv/measure')).toBe(false)
  })

  it('strips client-supplied internal and authorization headers', () => {
    const maliciousHeaders = {
      'host': 'joint-inspection.vercel.app',
      'user-agent': 'Mozilla/5.0',
      'x-serverless-authorization': 'Bearer forged-token',
      'x-vercel-oidc-token': 'attacker-oidc',
      'x-forwarded-for': '10.0.0.1, 192.168.1.1',
      'x-internal-secret': 'bypass-key',
      'x-gcp-project': 'fake-project',
      'x-service-account-email': 'fake@gcp.com',
      'accept': 'application/json',
    }

    const cleaned = sanitizeForwardHeaders(maliciousHeaders)

    expect(cleaned['host']).toBe('joint-inspection.vercel.app')
    expect(cleaned['accept']).toBe('application/json')
    expect(cleaned['x-serverless-authorization']).toBeUndefined()
    expect(cleaned['x-vercel-oidc-token']).toBeUndefined()
    expect(cleaned['x-forwarded-for']).toBeUndefined()
    expect(cleaned['x-internal-secret']).toBeUndefined()
    expect(cleaned['x-gcp-project']).toBeUndefined()
    expect(cleaned['x-service-account-email']).toBeUndefined()
  })

  it('validates image magic bytes accurately', () => {
    // JPEG (FF D8 FF)
    const jpegHeader = Buffer.from([0xff, 0xd8, 0xff, 0xe0])
    expect(validateMagicBytes(jpegHeader)).toBe(true)

    // PNG (89 50 4E 47 0D 0A 1A 0A)
    const pngHeader = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])
    expect(validateMagicBytes(pngHeader)).toBe(true)

    // WebP (RIFF....WEBP)
    const webpHeader = Buffer.from('RIFF1234WEBP', 'ascii')
    expect(validateMagicBytes(webpHeader)).toBe(true)

    // Foreign bash script
    const scriptHeader = Buffer.from('#!/bin/bash\n')
    expect(validateMagicBytes(scriptHeader)).toBe(false)

    // Truncated buffer
    expect(validateMagicBytes(Buffer.from([0x00]))).toBe(false)
  })

  it('enforces rate limiting when thresholds are exceeded', async () => {
    const mockReq = {
      headers: { 'x-real-ip': '198.51.100.25' },
      url: '/api/v1/cv/measure/multi-frame',
      method: 'POST',
    }

    // Limit for multi-frame is 5 requests/minute
    let lastResult
    for (let i = 0; i < 7; i++) {
      lastResult = await checkRateLimit(mockReq, 'multi-frame')
    }

    expect(lastResult?.allowed).toBe(false)
    expect(lastResult?.remaining).toBe(0)
    expect(lastResult?.resetSeconds).toBeGreaterThan(0)
  })

  it('provides neutral user auth abstraction for disabled and provider modes', async () => {
    const disabledProvider = new DisabledUserAuthProvider()
    const userDisabled = await disabledProvider.verifyRequest({})
    expect(userDisabled).not.toBeNull()
    expect(userDisabled?.roles).toContain('INSPECTOR')

    const pluggableProvider = new PluggableUserAuthProvider()
    const userNoToken = await pluggableProvider.verifyRequest({ headers: {} })
    expect(userNoToken).toBeNull()

    const userWithToken = await pluggableProvider.verifyRequest({
      headers: { authorization: 'Bearer valid.jwt.token' },
    })
    expect(userWithToken?.id).toBe('authenticated-user')
  })
})
