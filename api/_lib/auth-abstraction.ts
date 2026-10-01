/**
 * Provider-Neutral User Authentication Abstraction
 *
 * Implements a decoupling interface for end-user authentication.
 * Allows pluggable integration of Firebase, Auth0, Supabase, Clerk, Auth.js
 * or enterprise SSO without modifying the core AI/CV measurement engine.
 */

import { GATEWAY_CONFIG } from './config'

export interface AuthenticatedUser {
  id: string
  email?: string
  roles: string[]
  metadata?: Record<string, unknown>
}

export interface UserAuthProvider {
  readonly providerName: string
  verifyRequest(request: any): Promise<AuthenticatedUser | null>
}

/**
 * Disabled mode provider - active until final authentication vendor is approved.
 * Bypasses user identity check while maintaining strict zero-trust network boundaries.
 */
export class DisabledUserAuthProvider implements UserAuthProvider {
  readonly providerName = 'disabled'

  async verifyRequest(_request: any): Promise<AuthenticatedUser | null> {
    return {
      id: 'anonymous-inspections',
      roles: ['INSPECTOR'],
    }
  }
}

/**
 * Pluggable provider adapter stub for future production authentication selection.
 * Validates bearer JWT / session cookie from chosen auth vendor.
 */
export class PluggableUserAuthProvider implements UserAuthProvider {
  readonly providerName = 'provider'

  async verifyRequest(request: any): Promise<AuthenticatedUser | null> {
    const authHeader = request.headers['authorization'] || request.headers['Authorization']
    if (!authHeader || typeof authHeader !== 'string' || !authHeader.startsWith('Bearer ')) {
      return null
    }

    const token = authHeader.substring(7).trim()
    if (!token) {
      return null
    }

    // Provider token verification hook (e.g. Firebase Admin / Auth0 JWT / Supabase JWT)
    // NOTE: This will be bound to the chosen vendor's verification SDK once approved in USER_AUTH_DECISION.md
    return {
      id: 'authenticated-user',
      roles: ['INSPECTOR'],
    }
  }
}

// Instantiate active provider according to USER_AUTH_MODE
export const activeAuthProvider: UserAuthProvider =
  GATEWAY_CONFIG.USER_AUTH_MODE === 'provider'
    ? new PluggableUserAuthProvider()
    : new DisabledUserAuthProvider()

export async function verifyGatewayUser(request: any): Promise<AuthenticatedUser | null> {
  if (GATEWAY_CONFIG.USER_AUTH_MODE === 'disabled') {
    return activeAuthProvider.verifyRequest(request)
  }
  return activeAuthProvider.verifyRequest(request)
}
