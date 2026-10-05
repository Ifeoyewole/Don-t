// api/_lib/config.ts
var GATEWAY_CONFIG = {
  GCP_PROJECT_ID: process.env.GCP_PROJECT_ID || "joint-inspection-510310",
  GCP_PROJECT_NUMBER: process.env.GCP_PROJECT_NUMBER || "567370443508",
  GCP_SERVICE_ACCOUNT_EMAIL: process.env.GCP_SERVICE_ACCOUNT_EMAIL || "joint-inspect-vercel-invoker@joint-inspection-510310.iam.gserviceaccount.com",
  GCP_WORKLOAD_IDENTITY_POOL_ID: process.env.GCP_WORKLOAD_IDENTITY_POOL_ID || "vercel",
  GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID: process.env.GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID || "vercel-production",
  CLOUD_RUN_URL: (process.env.CLOUD_RUN_URL || "https://pipe-joint-api-7d5y5wcyta-nw.a.run.app").replace(/\/$/, ""),
  // Authentication abstraction mode ('disabled' until provider selection is approved)
  USER_AUTH_MODE: process.env.USER_AUTH_MODE || "disabled",
  // Rate Limiting (Requests / minute / IP)
  RATE_LIMITS: {
    HEALTH: parseInt(process.env.RATE_LIMIT_HEALTH || "60", 10),
    VALIDATION: parseInt(process.env.RATE_LIMIT_VALIDATION || "30", 10),
    MEASURE: parseInt(process.env.RATE_LIMIT_MEASURE || "20", 10),
    MULTI_FRAME: parseInt(process.env.RATE_LIMIT_MULTI_FRAME || "5", 10),
    CALIBRATION_READ: parseInt(process.env.RATE_LIMIT_CALIBRATION_READ || "30", 10),
    CALIBRATION_MUTATE: parseInt(process.env.RATE_LIMIT_CALIBRATION_MUTATE || "5", 10)
  },
  // Payload constraints
  MAX_UPLOAD_SIZE_BYTES: 15 * 1024 * 1024,
  // 15 MB
  MAX_MULTI_FRAME_BYTES: 30 * 1024 * 1024,
  // 30 MB
  MAX_MULTI_FRAME_COUNT: 30,
  // Allowed image MIME types
  ALLOWED_IMAGE_MIMES: ["image/jpeg", "image/png", "image/webp"]
};
var isProduction = process.env.NODE_ENV === "production" || process.env.VERCEL_ENV === "production";
if (isProduction) {
  if (process.env.DEV_CLOUD_RUN_ID_TOKEN) {
    delete process.env.DEV_CLOUD_RUN_ID_TOKEN;
  }
  if (process.env.TEST_VERCEL_OIDC_TOKEN) {
    delete process.env.TEST_VERCEL_OIDC_TOKEN;
  }
}
var ALLOWED_ORIGINS = [
  "https://joint-inspection.vercel.app",
  ...process.env.NODE_ENV !== "production" ? ["http://localhost:5173", "http://127.0.0.1:5173"] : []
];

// api/_lib/auth-abstraction.ts
var DisabledUserAuthProvider = class {
  providerName = "disabled";
  async verifyRequest(_request) {
    return {
      id: "anonymous-inspections",
      roles: ["INSPECTOR"]
    };
  }
};
var PluggableUserAuthProvider = class {
  providerName = "provider";
  async verifyRequest(request) {
    const authHeader = request.headers["authorization"] || request.headers["Authorization"];
    if (!authHeader || typeof authHeader !== "string" || !authHeader.startsWith("Bearer ")) {
      return null;
    }
    const token = authHeader.substring(7).trim();
    if (!token) {
      return null;
    }
    return {
      id: "authenticated-user",
      roles: ["INSPECTOR"]
    };
  }
};
var activeAuthProvider = GATEWAY_CONFIG.USER_AUTH_MODE === "provider" ? new PluggableUserAuthProvider() : new DisabledUserAuthProvider();
async function verifyGatewayUser(request) {
  if (GATEWAY_CONFIG.USER_AUTH_MODE === "disabled") {
    return activeAuthProvider.verifyRequest(request);
  }
  return activeAuthProvider.verifyRequest(request);
}

// api/_lib/rate-limiter.ts
var MemoryRateLimitStore = class {
  hits = /* @__PURE__ */ new Map();
  async increment(key, windowSeconds) {
    const now = Date.now();
    const entry = this.hits.get(key);
    if (!entry || entry.expiresAt <= now) {
      const expiresAt = now + windowSeconds * 1e3;
      this.hits.set(key, { count: 1, expiresAt });
      return { count: 1, ttl: windowSeconds };
    }
    entry.count += 1;
    const ttl = Math.max(1, Math.ceil((entry.expiresAt - now) / 1e3));
    return { count: entry.count, ttl };
  }
};
var activeStore = new MemoryRateLimitStore();
function getClientIp(req) {
  const vercelIp = req.headers["x-vercel-forwarded-for"];
  if (typeof vercelIp === "string" && vercelIp.trim()) {
    return vercelIp.split(",")[0].trim();
  }
  const xRealIp = req.headers["x-real-ip"];
  if (typeof xRealIp === "string" && xRealIp.trim()) {
    return xRealIp.trim();
  }
  return req.socket?.remoteAddress || "127.0.0.1";
}
function getRouteCategory(path, method) {
  const normalized = path.toLowerCase();
  if (normalized.includes("/health")) return "health";
  if (normalized.includes("/validate-photo")) return "validation";
  if (normalized.includes("/multi-frame")) return "multi-frame";
  if (normalized.includes("/measure")) return "measure";
  if (normalized.includes("/calibration")) {
    return ["POST", "PUT", "DELETE", "PATCH"].includes(method.toUpperCase()) ? "calibration-mutate" : "calibration-read";
  }
  return "measure";
}
async function checkRateLimit(req, routeCategory) {
  const ip = getClientIp(req);
  const category = routeCategory || getRouteCategory(req.url || "", req.method || "GET");
  let limit = GATEWAY_CONFIG.RATE_LIMITS.MEASURE;
  if (category === "health") limit = GATEWAY_CONFIG.RATE_LIMITS.HEALTH;
  else if (category === "validation") limit = GATEWAY_CONFIG.RATE_LIMITS.VALIDATION;
  else if (category === "multi-frame") limit = GATEWAY_CONFIG.RATE_LIMITS.MULTI_FRAME;
  else if (category === "calibration-read") limit = GATEWAY_CONFIG.RATE_LIMITS.CALIBRATION_READ;
  else if (category === "calibration-mutate") limit = GATEWAY_CONFIG.RATE_LIMITS.CALIBRATION_MUTATE;
  const key = `ratelimit:${category}:${ip}`;
  const { count, ttl } = await activeStore.increment(key, 60);
  const allowed = count <= limit;
  const remaining = Math.max(0, limit - count);
  return {
    allowed,
    current: count,
    limit,
    remaining,
    resetSeconds: ttl
  };
}

// api/_lib/gateway-guard.ts
import { randomUUID } from "node:crypto";
var FORBIDDEN_HEADER_PREFIXES = [
  "authorization",
  "x-serverless-authorization",
  "x-vercel-oidc-token",
  "x-internal-",
  "x-gcp-",
  "x-service-account-"
];
var MALICIOUS_PATH_PATTERNS = [
  /wp-admin/i,
  /\.env/i,
  /\/\.git/i,
  /phpmyadmin/i,
  /server-status/i,
  /\.aws/i,
  /\.ssh/i,
  /etc\/passwd/i
];
function isMaliciousPath(path) {
  return MALICIOUS_PATH_PATTERNS.some((pattern) => pattern.test(path));
}
function normalizeRequestId(rawId) {
  if (typeof rawId === "string") {
    const trimmed = rawId.trim();
    if (trimmed.length > 0 && trimmed.length <= 64 && /^[a-zA-Z0-9_-]+$/.test(trimmed)) {
      return trimmed;
    }
  }
  return `req_${Date.now()}_${randomUUID().slice(0, 8)}`;
}
function sanitizeForwardHeaders(headers) {
  const clean = {};
  for (const [key, value] of Object.entries(headers)) {
    if (!value || typeof value !== "string") continue;
    const lowerKey = key.toLowerCase();
    if (FORBIDDEN_HEADER_PREFIXES.some((prefix) => lowerKey.startsWith(prefix))) {
      continue;
    }
    if (lowerKey === "x-forwarded-for" || lowerKey === "x-forwarded-host") {
      continue;
    }
    clean[key] = value;
  }
  return clean;
}
function resolveGatewayRoute(url, method) {
  const [rawPath] = url.split("?");
  let cleanPath = rawPath.replace(/\/+/g, "/").replace(/\/$/, "");
  if (!cleanPath.startsWith("/")) {
    cleanPath = `/${cleanPath}`;
  }
  let subPath = cleanPath;
  if (subPath.startsWith("/api/v1/cv")) {
    subPath = subPath.substring("/api/v1/cv".length);
  } else if (subPath.startsWith("/api/v1")) {
    subPath = subPath.substring("/api/v1".length);
  } else if (subPath.startsWith("/cv")) {
    subPath = subPath.substring("/cv".length);
  }
  if (!subPath.startsWith("/")) {
    subPath = `/${subPath}`;
  }
  const upperMethod = method.toUpperCase();
  if (subPath === "/health") {
    if (upperMethod === "GET") {
      return {
        allowed: true,
        status: 200,
        targetPath: "api/v1/cv/health",
        routeCategory: "health",
        requiresAuth: false,
        requiresAdmin: false
      };
    }
    return { allowed: false, status: 405, routeCategory: "health", requiresAuth: false, requiresAdmin: false };
  }
  if (subPath === "/validate-photo") {
    if (upperMethod === "POST") {
      return {
        allowed: true,
        status: 200,
        targetPath: "api/v1/cv/validate-photo",
        routeCategory: "validation",
        requiresAuth: false,
        requiresAdmin: false
      };
    }
    return { allowed: false, status: 405, routeCategory: "validation", requiresAuth: false, requiresAdmin: false };
  }
  if (subPath === "/measure") {
    if (upperMethod === "POST") {
      return {
        allowed: true,
        status: 200,
        targetPath: "api/v1/cv/measure",
        routeCategory: "measure",
        requiresAuth: false,
        requiresAdmin: false
      };
    }
    return { allowed: false, status: 405, routeCategory: "measure", requiresAuth: false, requiresAdmin: false };
  }
  if (subPath === "/measure/multi-frame") {
    if (upperMethod === "POST") {
      return {
        allowed: true,
        status: 200,
        targetPath: "api/v1/cv/measure/multi-frame",
        routeCategory: "multi-frame",
        requiresAuth: false,
        requiresAdmin: false
      };
    }
    return { allowed: false, status: 405, routeCategory: "multi-frame", requiresAuth: false, requiresAdmin: false };
  }
  if (subPath === "/calibration/profiles") {
    if (upperMethod === "GET") {
      return {
        allowed: true,
        status: 200,
        targetPath: "api/v1/cv/calibration/profiles",
        routeCategory: "calibration-read",
        requiresAuth: true,
        requiresAdmin: false
      };
    }
    if (upperMethod === "POST") {
      return {
        allowed: true,
        status: 201,
        targetPath: "api/v1/cv/calibration/profiles",
        routeCategory: "calibration-mutate",
        requiresAuth: true,
        requiresAdmin: true
      };
    }
    return { allowed: false, status: 405, routeCategory: "calibration-read", requiresAuth: false, requiresAdmin: false };
  }
  const profileMatch = subPath.match(/^\/calibration\/profiles\/([a-zA-Z0-9_-]+)$/);
  if (profileMatch) {
    const cameraId = profileMatch[1];
    if (upperMethod === "GET") {
      return {
        allowed: true,
        status: 200,
        targetPath: `api/v1/cv/calibration/profiles/${cameraId}`,
        routeCategory: "calibration-read",
        requiresAuth: true,
        requiresAdmin: false
      };
    }
    return { allowed: false, status: 405, routeCategory: "calibration-read", requiresAuth: false, requiresAdmin: false };
  }
  return {
    allowed: false,
    status: 404,
    routeCategory: "health",
    requiresAuth: false,
    requiresAdmin: false
  };
}
var PayloadTooLargeError = class extends Error {
  constructor(message) {
    super(message);
    this.name = "PayloadTooLargeError";
  }
};
async function readStreamWithLimit(stream, maxBytes) {
  const chunks = [];
  let totalBytes = 0;
  for await (const chunk of stream) {
    const buf = typeof chunk === "string" ? Buffer.from(chunk) : chunk;
    totalBytes += buf.length;
    if (totalBytes > maxBytes) {
      throw new PayloadTooLargeError(
        `Payload exceeded real byte limit (${totalBytes} > ${maxBytes} bytes). Transfer aborted.`
      );
    }
    chunks.push(buf);
  }
  return Buffer.concat(chunks);
}
function sanitizeErrorResponse(_error, requestId) {
  return {
    detail: "An error occurred while processing the inspection request.",
    request_id: requestId
  };
}

// api/_lib/gcp-oidc.ts
import { getVercelOidcToken } from "@vercel/oidc";
var cachedIdToken = null;
async function getCloudRunIdToken() {
  const now = Date.now();
  if (cachedIdToken && cachedIdToken.expiresAtMs > now + 3e5) {
    return cachedIdToken.token;
  }
  const isProduction2 = process.env.NODE_ENV === "production" || process.env.VERCEL_ENV === "production";
  let vercelOidcToken = null;
  try {
    vercelOidcToken = await getVercelOidcToken();
  } catch {
    if (!isProduction2) {
      vercelOidcToken = process.env.VERCEL_OIDC_TOKEN || process.env.TEST_VERCEL_OIDC_TOKEN || null;
    }
  }
  if (!vercelOidcToken) {
    if (!isProduction2 && process.env.DEV_CLOUD_RUN_ID_TOKEN) {
      return process.env.DEV_CLOUD_RUN_ID_TOKEN;
    }
    return null;
  }
  const stsAudience = `//iam.googleapis.com/projects/${GATEWAY_CONFIG.GCP_PROJECT_NUMBER}/locations/global/workloadIdentityPools/${GATEWAY_CONFIG.GCP_WORKLOAD_IDENTITY_POOL_ID}/providers/${GATEWAY_CONFIG.GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID}`;
  try {
    const stsResponse = await fetch("https://sts.googleapis.com/v1/token", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json"
      },
      body: JSON.stringify({
        grant_type: "urn:ietf:params:oauth:grant-type:token-exchange",
        audience: stsAudience,
        scope: "https://www.googleapis.com/auth/cloud-platform",
        requested_token_type: "urn:ietf:params:oauth:token-type:access_token",
        subject_token_type: "urn:ietf:params:oauth:token-type:id_token",
        subject_token: vercelOidcToken
      })
    });
    if (!stsResponse.ok) {
      const errorText = await stsResponse.text().catch(() => "");
      throw new Error(`Google STS token exchange failed (${stsResponse.status}): ${errorText}`);
    }
    const stsData = await stsResponse.json();
    const stsAccessToken = stsData.access_token;
    const iamEndpoint = `https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/${encodeURIComponent(
      GATEWAY_CONFIG.GCP_SERVICE_ACCOUNT_EMAIL
    )}:generateIdToken`;
    const idTokenResponse = await fetch(iamEndpoint, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${stsAccessToken}`,
        "Content-Type": "application/json",
        Accept: "application/json"
      },
      body: JSON.stringify({
        audience: GATEWAY_CONFIG.CLOUD_RUN_URL,
        includeEmail: true
      })
    });
    if (!idTokenResponse.ok) {
      const errorText = await idTokenResponse.text().catch(() => "");
      throw new Error(`Cloud Run ID token generation failed (${idTokenResponse.status}): ${errorText}`);
    }
    const idTokenData = await idTokenResponse.json();
    const idToken = idTokenData.token;
    const ttlMs = (stsData.expires_in || 3600) * 1e3;
    cachedIdToken = {
      token: idToken,
      expiresAtMs: now + ttlMs
    };
    return idToken;
  } catch (error) {
    console.error("Workload Identity Federation exchange failure:", error);
    return null;
  }
}

// api/v1/cv/[...route].ts
function sendJson(res, statusCode, data, extraHeaders = {}) {
  const payload = JSON.stringify(data);
  res.writeHead(statusCode, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(payload),
    ...extraHeaders
  });
  res.end(payload);
}
function getMatchedOrigin(req) {
  const rawOrigin = req.headers.origin;
  if (!rawOrigin || typeof rawOrigin !== "string") return null;
  const cleanOrigin = rawOrigin.trim();
  if (ALLOWED_ORIGINS.includes(cleanOrigin)) {
    return cleanOrigin;
  }
  return null;
}
async function handler(req, res) {
  let requestId = "unknown";
  const corsHeaders = {
    "Vary": "Origin"
  };
  try {
    requestId = normalizeRequestId(req.headers["x-request-id"]);
    const method = req.method?.toUpperCase() || "GET";
    const url = req.url || "/";
    const matchedOrigin = getMatchedOrigin(req);
    if (matchedOrigin) {
      corsHeaders["Access-Control-Allow-Origin"] = matchedOrigin;
      corsHeaders["Access-Control-Allow-Credentials"] = "true";
    }
    if (method === "OPTIONS") {
      if (!matchedOrigin) {
        return sendJson(res, 403, { detail: "Forbidden origin", request_id: requestId }, corsHeaders);
      }
      res.writeHead(204, {
        ...corsHeaders,
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Request-ID",
        "Access-Control-Max-Age": "86400"
      });
      return res.end();
    }
    if (isMaliciousPath(url)) {
      return sendJson(res, 404, { detail: "Not found", request_id: requestId }, corsHeaders);
    }
    const route = resolveGatewayRoute(url, method);
    if (!route.allowed) {
      return sendJson(
        res,
        route.status,
        {
          detail: route.status === 405 ? "Method not allowed" : "Not found",
          request_id: requestId
        },
        corsHeaders
      );
    }
    const rateLimitResult = await checkRateLimit(req, route.routeCategory);
    if (!rateLimitResult.allowed) {
      return sendJson(
        res,
        429,
        {
          detail: "Rate limit exceeded. Too many requests submitted.",
          request_id: requestId,
          retry_after_seconds: rateLimitResult.resetSeconds
        },
        {
          ...corsHeaders,
          "Retry-After": String(rateLimitResult.resetSeconds)
        }
      );
    }
    const authUser = await verifyGatewayUser(req);
    if (GATEWAY_CONFIG.USER_AUTH_MODE === "provider" && !authUser) {
      return sendJson(
        res,
        401,
        {
          detail: "Authentication required. Invalid or missing credentials.",
          request_id: requestId
        },
        corsHeaders
      );
    }
    if (route.requiresAuth && !authUser) {
      return sendJson(
        res,
        401,
        {
          detail: "Authentication required to access calibration profiles.",
          request_id: requestId
        },
        corsHeaders
      );
    }
    if (route.requiresAdmin) {
      const hasAdminRole = authUser?.roles?.includes("ADMIN");
      if (!hasAdminRole) {
        return sendJson(
          res,
          403,
          {
            detail: "Administrative authority required for calibration mutation.",
            request_id: requestId
          },
          corsHeaders
        );
      }
    }
    const [, rawQuery] = url.split("?");
    const qParams = new URLSearchParams(rawQuery || "");
    qParams.delete("...route");
    qParams.delete("route");
    if (route.targetPath === "api/v1/cv/health") {
      const wantsDiagnostics = qParams.get("diagnostics") === "true";
      const isEngineerOrAdmin = authUser?.roles?.includes("ENGINEER") || authUser?.roles?.includes("ADMIN");
      if (!wantsDiagnostics || !isEngineerOrAdmin) {
        return sendJson(res, 200, { status: "ok" }, corsHeaders);
      }
    }
    const maxAllowedBytes = route.routeCategory === "multi-frame" ? GATEWAY_CONFIG.MAX_MULTI_FRAME_BYTES : GATEWAY_CONFIG.MAX_UPLOAD_SIZE_BYTES;
    let bodyBuffer;
    if (["POST", "PUT", "PATCH"].includes(method)) {
      try {
        bodyBuffer = await readStreamWithLimit(req, maxAllowedBytes);
      } catch (err) {
        if (err instanceof PayloadTooLargeError) {
          return sendJson(
            res,
            413,
            {
              detail: err.message,
              request_id: requestId
            },
            corsHeaders
          );
        }
        return sendJson(res, 400, { detail: "Failed reading request payload", request_id: requestId }, corsHeaders);
      }
    }
    const idToken = await getCloudRunIdToken();
    const forwardHeaders = sanitizeForwardHeaders(req.headers);
    forwardHeaders["x-request-id"] = requestId;
    if (idToken) {
      forwardHeaders["x-serverless-authorization"] = `Bearer ${idToken}`;
      forwardHeaders["authorization"] = `Bearer ${idToken}`;
    }
    const forwardQuery = qParams.toString() ? `?${qParams.toString()}` : "";
    const targetUrl = `${GATEWAY_CONFIG.CLOUD_RUN_URL}/${route.targetPath}${forwardQuery}`;
    try {
      const upstreamResponse = await fetch(targetUrl, {
        method,
        headers: forwardHeaders,
        body: bodyBuffer
      });
      const responseBody = await upstreamResponse.arrayBuffer();
      const contentType = upstreamResponse.headers.get("content-type") || "application/json";
      res.writeHead(upstreamResponse.status, {
        ...corsHeaders,
        "Content-Type": contentType,
        "X-Request-ID": requestId,
        "Cache-Control": "no-store, max-age=0"
      });
      res.end(Buffer.from(responseBody));
    } catch (error) {
      console.error(`[GATEWAY-ERR-${requestId}] Upstream invocation failed:`, error);
      const sanitized = sanitizeErrorResponse(error, requestId);
      return sendJson(res, 502, sanitized, corsHeaders);
    }
  } catch (fatalError) {
    console.error(`[GATEWAY-FATAL-${requestId}]`, fatalError);
    return sendJson(res, 500, { detail: "Gateway Internal Server Error", request_id: requestId }, corsHeaders);
  }
}
export {
  handler as default
};
