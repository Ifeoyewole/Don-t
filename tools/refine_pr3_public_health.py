from pathlib import Path

path = Path('api/v1/cv/[...route].js')
text = path.read_text(encoding='utf-8')
old = '''    if (route.targetPath === "api/v1/cv/health") {\n      const wantsDiagnostics = qParams.get("diagnostics") === "true";\n      const isEngineerOrAdmin = authUser?.roles?.includes("ENGINEER") || authUser?.roles?.includes("ADMIN");\n      if (!wantsDiagnostics || !isEngineerOrAdmin) {\n        return sendJson(res, 200, { status: "ok" }, corsHeaders);\n      }\n    }'''
new = '''    let sanitizePublicHealth = false;\n    if (route.targetPath === "api/v1/cv/health") {\n      const wantsDiagnostics = qParams.get("diagnostics") === "true";\n      const isEngineerOrAdmin = authUser?.roles?.includes("ENGINEER") || authUser?.roles?.includes("ADMIN");\n      sanitizePublicHealth = !wantsDiagnostics || !isEngineerOrAdmin;\n    }'''
if old not in text:
    raise RuntimeError('Public health short-circuit block not found')
text = text.replace(old, new, 1)

old2 = '''      const responseBody = await upstreamResponse.arrayBuffer();\n      const contentType = upstreamResponse.headers.get("content-type") || "application/json";\n      res.writeHead(upstreamResponse.status, {\n        ...corsHeaders,\n        "Content-Type": contentType,\n        "X-Request-ID": requestId,\n        "Cache-Control": "no-store, max-age=0"\n      });\n      res.end(Buffer.from(responseBody));'''
new2 = '''      if (sanitizePublicHealth) {\n        const healthPayload = await upstreamResponse.json().catch(() => null);\n        if (!upstreamResponse.ok || !healthPayload || typeof healthPayload !== "object") {\n          return sendJson(\n            res,\n            upstreamResponse.ok ? 502 : upstreamResponse.status,\n            { status: "unavailable", request_id: requestId },\n            { ...corsHeaders, "X-Request-ID": requestId, "Cache-Control": "no-store, max-age=0" }\n          );\n        }\n        const wrc = healthPayload.external_models?.wrc_inceptionresnetv2;\n        return sendJson(\n          res,\n          200,\n          {\n            status: healthPayload.status === "ok" ? "ok" : "degraded",\n            version: typeof healthPayload.version === "string" ? healthPayload.version : undefined,\n            opencv_version: typeof healthPayload.opencv_version === "string" ? healthPayload.opencv_version : undefined,\n            external_models: {\n              wrc_inceptionresnetv2: {\n                enabled: Boolean(wrc?.enabled),\n                loaded: Boolean(wrc?.loaded)\n              }\n            }\n          },\n          { ...corsHeaders, "X-Request-ID": requestId, "Cache-Control": "no-store, max-age=0" }\n        );\n      }\n      const responseBody = await upstreamResponse.arrayBuffer();\n      const contentType = upstreamResponse.headers.get("content-type") || "application/json";\n      res.writeHead(upstreamResponse.status, {\n        ...corsHeaders,\n        "Content-Type": contentType,\n        "X-Request-ID": requestId,\n        "Cache-Control": "no-store, max-age=0"\n      });\n      res.end(Buffer.from(responseBody));'''
if old2 not in text:
    raise RuntimeError('Upstream relay block not found')
text = text.replace(old2, new2, 1)
path.write_text(text, encoding='utf-8')
print('sanitized public health readiness enabled')
